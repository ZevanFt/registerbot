"""OpenAI-compatible proxy routes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from src.config.settings import load_settings
from src.integrations.openai_api import OpenAIChatClient
from src.middleware.auth import OpenAIProxyException, TokenContext, build_openai_error, require_bearer_token
from src.services.account_pool import AccountPool, NoAvailableAccountError
from src.storage.account_store import AccountStore
from src.storage.stats_store import StatsStore
from src.storage.token_store import TokenStore

router = APIRouter(tags=["openai-proxy"])
_account_pool: AccountPool | None = None


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False

    model_config = ConfigDict(extra="allow")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_token_store() -> TokenStore:
    settings = load_settings()
    return TokenStore(settings.storage.tokens_db_path)


def _build_stats_store() -> StatsStore:
    settings = load_settings()
    return StatsStore(settings.storage.stats_db_path)


def _build_account_store() -> AccountStore:
    settings = load_settings()
    return AccountStore(settings.storage.db_path, settings.storage.encryption_key)


def _build_account_pool() -> AccountPool:
    global _account_pool
    settings = load_settings()
    if _account_pool is None:
        _account_pool = AccountPool(
            account_store=_build_account_store(),
            cooldown_seconds=settings.proxy.cooldown_seconds,
            failure_threshold=settings.proxy.failure_threshold,
        )
    return _account_pool


def _build_chat_client() -> OpenAIChatClient:
    settings = load_settings()
    proxy = settings.network.openai_proxy or settings.network.http_proxy
    return OpenAIChatClient(
        base_url=settings.openai.base_url,
        timeout=settings.openai.timeout_seconds,
        stream_timeout=settings.openai.stream_timeout_seconds,
        proxy=proxy,
    )


def _extract_error(status_code: int, body: Any) -> tuple[str, str, str]:
    fallback_message = f"Upstream service returned {status_code}"
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = str(error.get("message", fallback_message))
            error_type = str(error.get("type", "upstream_error"))
            code = str(error.get("code", status_code))
            return message, error_type, code
    return fallback_message, "upstream_error", str(status_code)


def _is_quota_error(status_code: int, body: Any) -> bool:
    """Detect daily quota exhaustion (429 rate_limit / insufficient_quota)."""
    if status_code != 429:
        return False
    if isinstance(body, dict):
        error = body.get("error", {})
        if isinstance(error, dict):
            code = str(error.get("code", ""))
            error_type = str(error.get("type", ""))
            if code in {"rate_limit_exceeded", "insufficient_quota"}:
                return True
            if error_type == "insufficient_quota":
                return True
    return True  # 429 without details → treat as quota limit


def _record_usage(
    token_id: int,
    account_id: int | None,
    model: str | None,
    request_tokens: int,
    response_tokens: int,
    status_code: int,
) -> None:
    token_store = _build_token_store()
    token_store.update_usage(token_id=token_id, request_inc=1, token_inc=request_tokens + response_tokens)
    stats_store = _build_stats_store()
    stats_store.append_usage_log(
        timestamp=_now_iso(),
        account_id=account_id,
        model=model,
        request_tokens=request_tokens,
        response_tokens=response_tokens,
        status_code=status_code,
    )


@router.get("/v1/models")
async def list_models(_: TokenContext = Depends(require_bearer_token)) -> JSONResponse:
    pool = _build_account_pool()
    account: dict[str, Any] | None = None
    try:
        account = pool.acquire_account()
        payload = await _build_chat_client().list_models(str(account["openai_token"]))
        pool.mark_success(int(account["id"]))
        return JSONResponse(status_code=200, content=payload)
    except NoAvailableAccountError as exc:
        raise OpenAIProxyException(503, str(exc), "service_unavailable", "no_available_account") from exc
    except httpx.TimeoutException as exc:
        if account is not None:
            pool.mark_failure(int(account["id"]), "timeout")
        raise OpenAIProxyException(504, "Upstream timeout", "timeout_error", "upstream_timeout") from exc
    except httpx.HTTPStatusError as exc:
        body: dict[str, Any] | str
        try:
            body = exc.response.json()
        except ValueError:
            body = {}
        if account is not None:
            if _is_quota_error(exc.response.status_code, body):
                pool.mark_usage_limited(int(account["id"]))
            else:
                pool.mark_failure(int(account["id"]), f"status_{exc.response.status_code}")
        message, error_type, code = _extract_error(exc.response.status_code, body)
        raise OpenAIProxyException(exc.response.status_code, message, error_type, code) from exc
    except httpx.RequestError as exc:
        if account is not None:
            pool.mark_failure(int(account["id"]), "request_error")
        raise OpenAIProxyException(502, f"Upstream request failed: {exc}", "api_error", "bad_gateway") from exc


@router.post("/v1/chat/completions")
async def chat_completions(
    payload: ChatCompletionRequest,
    token: TokenContext = Depends(require_bearer_token),
):
    pool = _build_account_pool()
    account: dict[str, Any] | None = None
    model = payload.model
    raw_payload = payload.model_dump(exclude_none=True)

    try:
        account = pool.acquire_account()
    except NoAvailableAccountError as exc:
        raise OpenAIProxyException(503, str(exc), "service_unavailable", "no_available_account") from exc

    if bool(raw_payload.get("stream")):

        async def _stream_with_usage() -> Any:
            status_code = 200
            try:
                async for chunk in _build_chat_client().chat_completions_stream(
                    str(account["openai_token"]),
                    raw_payload,
                ):
                    if chunk:
                        yield chunk
                pool.mark_success(int(account["id"]))
            except Exception as exc:  # pragma: no cover
                status_code = 500
                pool.mark_failure(int(account["id"]), str(exc))
                error = build_openai_error(
                    message=f"Streaming proxy failed: {exc}",
                    error_type="api_error",
                    code="stream_proxy_error",
                )
                yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n".encode("utf-8")
                yield b"data: [DONE]\n\n"
            finally:
                _record_usage(
                    token_id=token.token_id,
                    account_id=int(account["id"]),
                    model=model,
                    request_tokens=0,
                    response_tokens=0,
                    status_code=status_code,
                )

        return StreamingResponse(_stream_with_usage(), media_type="text/event-stream")

    try:
        status_code, body = await _build_chat_client().chat_completions(
            str(account["openai_token"]),
            raw_payload,
        )
        if status_code >= 400:
            if _is_quota_error(status_code, body):
                pool.mark_usage_limited(int(account["id"]))
            else:
                pool.mark_failure(int(account["id"]), f"status_{status_code}")
            message, error_type, code = _extract_error(status_code, body)
            _record_usage(
                token_id=token.token_id,
                account_id=int(account["id"]),
                model=model,
                request_tokens=0,
                response_tokens=0,
                status_code=status_code,
            )
            raise OpenAIProxyException(status_code, message, error_type, code)

        usage = body.get("usage", {}) if isinstance(body, dict) else {}
        request_tokens = int(usage.get("prompt_tokens", 0))
        response_tokens = int(usage.get("completion_tokens", 0))
        _record_usage(
            token_id=token.token_id,
            account_id=int(account["id"]),
            model=model,
            request_tokens=request_tokens,
            response_tokens=response_tokens,
            status_code=status_code,
        )
        pool.mark_success(int(account["id"]))
        return JSONResponse(status_code=status_code, content=body)
    except httpx.TimeoutException as exc:
        pool.mark_failure(int(account["id"]), "timeout")
        _record_usage(
            token_id=token.token_id,
            account_id=int(account["id"]),
            model=model,
            request_tokens=0,
            response_tokens=0,
            status_code=504,
        )
        raise OpenAIProxyException(504, "Upstream timeout", "timeout_error", "upstream_timeout") from exc
    except httpx.RequestError as exc:
        pool.mark_failure(int(account["id"]), "request_error")
        _record_usage(
            token_id=token.token_id,
            account_id=int(account["id"]),
            model=model,
            request_tokens=0,
            response_tokens=0,
            status_code=502,
        )
        raise OpenAIProxyException(502, f"Upstream request failed: {exc}", "api_error", "bad_gateway") from exc


def openai_proxy_error_response(exc: OpenAIProxyException) -> JSONResponse:
    payload = build_openai_error(
        message=exc.message,
        error_type=exc.error_type,
        code=exc.code,
        param=exc.param,
    )
    return JSONResponse(status_code=exc.status_code, content=payload)
