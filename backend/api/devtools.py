"""DevTools API routes for test runs and log archive access."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel

from src.config.settings import load_settings
from src.integrations.openai_api import OpenAIChatClient, OpenAIRegistrationClient
from src.integrations.talentmail import TalentMailClient
from src.services.registration_service import RegistrationService
from src.storage.account_store import AccountStore
from src.utils.log_collector import LogCollector
from src.middleware.auth import require_admin_permission

api_router = APIRouter(
    prefix="/api/devtools",
    tags=["devtools"],
    dependencies=[Depends(require_admin_permission)],
)
ws_router = APIRouter()


class TestRunRequest(BaseModel):
    test_file: str | None = None


class ModelTruthProbeRequest(BaseModel):
    models: list[str] = []
    max_models: int = 8


class HttpRegistrationTestRequest(BaseModel):
    target: int = 1
    max_failures: int = 2
    delay_seconds: float = 2.0
    turnstile_token: str = ""
    use_proxy_pool: bool = True
    proxy_pool: list[str] = []


class HttpRiskProbeRequest(BaseModel):
    authorize_url: str = ""


class RegistrationTestRequest(HttpRegistrationTestRequest):
    mode: str = "http"


_HTTP_STAGE_LABELS: dict[str, str] = {
    "create_temp_email": "邮箱创建",
    "submit_registration": "注册提交",
    "wait_for_verification_code": "邮箱验证码获取",
    "verify_email": "邮箱验证",
    "verify_phone": "手机验证",
    "set_password": "Token 兑换",
    "set_profile": "资料设置",
    "upgrade_plus": "升级流程",
}

_BROWSER_STAGE_LABELS: dict[str, str] = {
    "create_temp_email": "邮箱创建",
    "browser_signup": "浏览器注册提交",
    "wait_for_verification_code": "邮箱验证码获取",
    "browser_verify_email": "浏览器邮箱验证",
    "verify_phone": "手机验证",
    "set_password": "Token 兑换",
    "set_profile": "资料设置",
    "upgrade_plus": "升级流程",
}

_CHALLENGE_MARKERS = [
    "just a moment",
    "cloudflare",
    "challenge",
    "captcha",
    "turnstile",
    "bot",
    "access denied",
    "forbidden",
    "http 403",
]


class _ProxyPoolSelector:
    """Round-robin style selector with failure/challenge cooldown."""

    def __init__(self, proxies: list[str], *, failure_threshold: int, challenge_threshold: int, cooldown_seconds: int) -> None:
        self._proxies = [item.strip() for item in proxies if item.strip()]
        self._idx = -1
        self._failure_threshold = max(1, failure_threshold)
        self._challenge_threshold = max(1, challenge_threshold)
        self._cooldown_seconds = max(1, cooldown_seconds)
        self._state: dict[str, dict[str, Any]] = {
            proxy: {
                "failures": 0,
                "challenge_hits": 0,
                "cooldown_until": None,
                "selected_count": 0,
                "success_count": 0,
            }
            for proxy in self._proxies
        }

    @property
    def enabled(self) -> bool:
        return bool(self._proxies)

    def pick(self) -> str:
        if not self._proxies:
            return ""
        now = datetime.now()
        size = len(self._proxies)
        for offset in range(1, size + 1):
            idx = (self._idx + offset) % size
            proxy = self._proxies[idx]
            state = self._state[proxy]
            cooldown_until = state.get("cooldown_until")
            if isinstance(cooldown_until, datetime) and cooldown_until > now:
                continue
            self._idx = idx
            state["selected_count"] = int(state.get("selected_count") or 0) + 1
            return proxy
        # All proxies are cooling down; pick the one that becomes available first.
        earliest = min(
            self._proxies,
            key=lambda p: self._state[p].get("cooldown_until") or now,
        )
        self._idx = self._proxies.index(earliest)
        self._state[earliest]["selected_count"] = int(self._state[earliest].get("selected_count") or 0) + 1
        return earliest

    def report(self, proxy: str, *, success: bool, challenge: bool) -> None:
        if not proxy or proxy not in self._state:
            return
        state = self._state[proxy]
        if success:
            state["failures"] = 0
            state["challenge_hits"] = 0
            state["cooldown_until"] = None
            state["success_count"] = int(state.get("success_count") or 0) + 1
            return

        state["failures"] = int(state.get("failures") or 0) + 1
        if challenge:
            state["challenge_hits"] = int(state.get("challenge_hits") or 0) + 1

        if int(state["failures"]) >= self._failure_threshold or int(state["challenge_hits"]) >= self._challenge_threshold:
            state["cooldown_until"] = datetime.now() + timedelta(seconds=self._cooldown_seconds)
            state["failures"] = 0
            state["challenge_hits"] = 0

    def snapshot(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for proxy in self._proxies:
            state = self._state[proxy]
            rows.append(
                {
                    "proxy": proxy,
                    "selected_count": int(state.get("selected_count") or 0),
                    "success_count": int(state.get("success_count") or 0),
                    "cooldown_until": state.get("cooldown_until").isoformat() if isinstance(state.get("cooldown_until"), datetime) else None,
                }
            )
        return rows


class TestRunManager:
    """Manage async pytest runs and stream output to subscribers."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._last_run: dict[str, Any] = {"run_id": None, "status": "idle", "output": []}
        self._current_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def start(self, test_file: str | None) -> str:
        async with self._lock:
            if self._current_task and not self._current_task.done():
                raise RuntimeError("A test run is already in progress")

            run_id = uuid.uuid4().hex
            self._last_run = {"run_id": run_id, "status": "running", "output": []}
            self._current_task = asyncio.create_task(self._run_pytest(run_id=run_id, test_file=test_file))
            return run_id

    async def get_last(self) -> dict[str, Any]:
        async with self._lock:
            return {
                "run_id": self._last_run.get("run_id"),
                "status": self._last_run.get("status"),
                "output": [dict(item) for item in self._last_run.get("output", [])],
            }

    async def _run_pytest(self, run_id: str, test_file: str | None) -> None:
        cmd = [".venv/bin/python", "-m", "pytest", "tests/", "-v", "--tb=short"]
        if test_file:
            cmd = [".venv/bin/python", "-m", "pytest", test_file, "-v", "--tb=short"]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async def read_stream(stream: asyncio.StreamReader | None, stream_type: str) -> None:
            if stream is None:
                return
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip("\r\n")
                await self._publish({"type": stream_type, "line": text, "run_id": run_id})

        await asyncio.gather(read_stream(process.stdout, "stdout"), read_stream(process.stderr, "stderr"))
        exit_code = await process.wait()
        summary = f"pytest finished with exit_code={exit_code}"
        await self._publish(
            {
                "type": "exit",
                "exit_code": exit_code,
                "summary": summary,
                "run_id": run_id,
            }
        )

        async with self._lock:
            if self._last_run.get("run_id") == run_id:
                self._last_run["status"] = "finished"

    async def _publish(self, event: dict[str, Any]) -> None:
        async with self._lock:
            self._last_run.setdefault("output", []).append(dict(event))
            clients = list(self._clients)

        stale_clients: list[WebSocket] = []
        for client in clients:
            try:
                await client.send_json(event)
            except Exception:
                stale_clients.append(client)

        if stale_clients:
            async with self._lock:
                for client in stale_clients:
                    self._clients.discard(client)


_test_run_manager = TestRunManager()


def get_test_manager() -> TestRunManager:
    return _test_run_manager


def _validate_test_file(test_file: str | None) -> str | None:
    if not test_file:
        return None
    path = Path(test_file)
    if path.is_absolute():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="test_file must be a relative path")
    resolved = path.resolve()
    tests_root = Path("tests").resolve()
    if tests_root not in resolved.parents and resolved != tests_root:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="test_file must be under tests/")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="test_file does not exist")
    return str(path)


def _build_account_store() -> AccountStore:
    settings = load_settings()
    return AccountStore(settings.storage.db_path, settings.storage.encryption_key)


def _build_chat_client(timeout_seconds: float = 45.0) -> OpenAIChatClient:
    settings = load_settings()
    proxy = settings.network.openai_proxy or settings.network.http_proxy
    if "localhost" in settings.openai.base_url or "127.0.0.1" in settings.openai.base_url:
        proxy = ""
    return OpenAIChatClient(
        base_url=settings.openai.base_url,
        timeout=min(settings.openai.timeout_seconds, timeout_seconds),
        stream_timeout=min(settings.openai.stream_timeout_seconds, timeout_seconds),
        proxy=proxy,
    )


def _default_probe_models() -> list[str]:
    # Keep probe list deterministic and short for operator usage.
    return [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4.1-mini",
        "gpt-4.1",
        "o3-mini",
        "o1-mini",
    ]


async def _pick_probe_token() -> str:
    store = _build_account_store()
    for account in store.list_accounts_with_health():
        token = str(account.get("openai_token") or "").strip()
        status_value = str(account.get("status") or "").strip().lower()
        runtime_status = str(account.get("runtime_status") or "").strip().lower()
        if token and status_value == "active" and (not runtime_status or runtime_status == "active"):
            return token
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No active account token available for model truth probe",
    )


async def _create_temp_email() -> str:
    settings = load_settings()
    async with TalentMailClient(
        base_url=settings.talentmail.base_url,
        email=settings.talentmail.email,
        password=settings.talentmail.password,
        proxy=settings.network.talentmail_proxy or settings.network.http_proxy,
    ) as mail_client:
        mailbox = await mail_client.create_temp_email()
    email = str(mailbox.get("email") or "").strip()
    if not email:
        raise RuntimeError("failed to create temp email")
    return email


def _stage_labels_by_mode(mode: str) -> dict[str, str]:
    if str(mode).strip().lower() == "browser":
        return _BROWSER_STAGE_LABELS
    return _HTTP_STAGE_LABELS


def _aggregate_stage_stats(attempts: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    stage_labels = _stage_labels_by_mode(mode)
    stage_totals: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        for item in attempt.get("step_results", []):
            step_key = str(item.get("step") or "").strip()
            if not step_key:
                continue
            bucket = stage_totals.setdefault(
                step_key,
                {
                    "step": step_key,
                    "label": stage_labels.get(step_key, step_key),
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "skipped": 0,
                },
            )
            bucket["total"] += 1
            status_text = str(item.get("status") or "").strip().lower()
            if status_text == "success":
                bucket["success"] += 1
            elif status_text == "skipped":
                bucket["skipped"] += 1
            else:
                bucket["failed"] += 1

    ordered = list(stage_labels.keys())
    ranked = sorted(
        stage_totals.values(),
        key=lambda row: ordered.index(row["step"]) if row["step"] in ordered else len(ordered),
    )
    for row in ranked:
        total = int(row["total"] or 0)
        row["success_rate"] = round((row["success"] / total) * 100, 2) if total > 0 else 0.0
    return ranked


def _is_challenge_error(errors: dict[str, Any]) -> bool:
    for value in errors.values():
        text = str(value or "").lower()
        for marker in _CHALLENGE_MARKERS:
            if marker in text:
                return True
    return False


@api_router.post("/test")
async def start_test_run(payload: TestRunRequest) -> dict[str, str]:
    validated_file = _validate_test_file(payload.test_file)
    manager = get_test_manager()
    try:
        run_id = await manager.start(validated_file)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {"run_id": run_id, "status": "started"}


@api_router.post("/models/truth-probe")
async def run_model_truth_probe(payload: ModelTruthProbeRequest) -> dict[str, Any]:
    models = [item.strip() for item in payload.models if item.strip()]
    if not models:
        models = _default_probe_models()
    max_models = min(max(int(payload.max_models or 1), 1), 20)
    models = models[:max_models]

    token = await _pick_probe_token()
    client = _build_chat_client(timeout_seconds=45.0)
    results: list[dict[str, Any]] = []
    for model_id in models:
        started_at = datetime.now().isoformat()
        try:
            status_code, body = await client.chat_completions(
                token,
                {
                    "model": model_id,
                    "messages": [{"role": "user", "content": "model truth probe"}],
                    "max_tokens": 1,
                },
            )
            body_dict = body if isinstance(body, dict) else {}
            error_payload = body_dict.get("error", {})
            error_message = ""
            if isinstance(error_payload, dict):
                error_message = str(error_payload.get("message") or "")
            results.append(
                {
                    "declared_model": model_id,
                    "status_code": status_code,
                    "probe_success": status_code < 400 and not error_message,
                    "actual_model": str(body_dict.get("model") or ""),
                    "error": error_message,
                    "started_at": started_at,
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "declared_model": model_id,
                    "status_code": 599,
                    "probe_success": False,
                    "actual_model": "",
                    "error": str(exc),
                    "started_at": started_at,
                }
            )

    success_count = sum(1 for item in results if bool(item.get("probe_success")))
    return {
        "total": len(results),
        "success": success_count,
        "failed": len(results) - success_count,
        "results": results,
    }


async def _run_registration_test(payload: HttpRegistrationTestRequest, mode: str) -> dict[str, Any]:
    run_mode = str(mode or "http").strip().lower()
    if run_mode not in {"http", "browser"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode must be http/browser")

    target = max(int(payload.target or 1), 1)
    max_failures = max(int(payload.max_failures or 1), 1)
    delay_seconds = max(float(payload.delay_seconds or 0), 0.0)

    settings = load_settings()
    original_mode = settings.registration.mode
    original_turnstile_token = settings.registration.http_turnstile_token
    original_openai_proxy = settings.network.openai_proxy
    settings.registration.mode = run_mode
    if run_mode == "http" and payload.turnstile_token.strip():
        settings.registration.http_turnstile_token = payload.turnstile_token.strip()

    configured_pool = [item for item in settings.network.openai_proxy_pool if str(item or "").strip()]
    request_pool = [item for item in payload.proxy_pool if str(item or "").strip()]
    effective_pool = request_pool if request_pool else configured_pool
    pool_selector = _ProxyPoolSelector(
        proxies=effective_pool,
        failure_threshold=max(1, settings.proxy.failure_threshold),
        challenge_threshold=2,
        cooldown_seconds=max(10, settings.proxy.cooldown_seconds),
    )

    password = str(settings.openai.default_password or "").strip()
    if not password:
        settings.registration.mode = original_mode
        settings.registration.http_turnstile_token = original_turnstile_token
        settings.network.openai_proxy = original_openai_proxy
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="openai.default_password is required for HTTP registration test",
        )

    service = RegistrationService(
        settings=settings,
        account_store=AccountStore(settings.storage.db_path, settings.storage.encryption_key),
    )
    started_at = datetime.now().isoformat()
    success_count = 0
    failure_count = 0
    attempts: list[dict[str, Any]] = []
    attempt_no = 0
    try:
        while success_count < target and failure_count < max_failures:
            attempt_no += 1
            selected_proxy = ""
            proxy_pool_active = bool(payload.use_proxy_pool and pool_selector.enabled and run_mode == "http")
            if proxy_pool_active:
                selected_proxy = pool_selector.pick()
                settings.network.openai_proxy = selected_proxy

            email = await _create_temp_email()
            result = await service.register_account(email=email, password=password)
            ok = bool(result.get("success"))
            error_map = result.get("errors", {})
            challenge_hit = _is_challenge_error(error_map if isinstance(error_map, dict) else {})
            if proxy_pool_active and selected_proxy:
                pool_selector.report(selected_proxy, success=ok, challenge=challenge_hit)
            attempts.append(
                {
                    "attempt": attempt_no,
                    "email": email,
                    "success": ok,
                    "proxy": selected_proxy,
                    "challenge_detected": challenge_hit,
                    "account_id": result.get("account_id"),
                    "total_duration": result.get("total_duration"),
                    "errors": error_map,
                    "step_results": result.get("step_results", []),
                }
            )
            if ok:
                success_count += 1
            else:
                failure_count += 1
            if success_count < target and failure_count < max_failures and delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
    finally:
        settings.registration.mode = original_mode
        settings.registration.http_turnstile_token = original_turnstile_token
        settings.network.openai_proxy = original_openai_proxy

    return {
        "started_at": started_at,
        "target": target,
        "attempts_total": len(attempts),
        "success_count": success_count,
        "failure_count": failure_count,
        "accounts_created": success_count,
        "success_rate": round((success_count / len(attempts)) * 100, 2) if attempts else 0.0,
        "mode": run_mode,
        "turnstile_token_set": bool(payload.turnstile_token.strip() or original_turnstile_token.strip()),
        "proxy_pool_enabled": bool(payload.use_proxy_pool and pool_selector.enabled and run_mode == "http"),
        "proxy_pool_size": len(effective_pool),
        "proxy_stats": pool_selector.snapshot(),
        "stage_stats": _aggregate_stage_stats(attempts, run_mode),
        "attempts": attempts,
    }


@api_router.post("/http-test")
async def run_http_registration_test_compat(payload: HttpRegistrationTestRequest) -> dict[str, Any]:
    """Backward-compatible alias for older frontend paths."""

    return await _run_registration_test(payload, mode="http")


@api_router.post("/registration/http-test")
async def run_http_registration_test(payload: HttpRegistrationTestRequest) -> dict[str, Any]:
    return await _run_registration_test(payload, mode="http")


@api_router.post("/registration/test")
async def run_registration_test(payload: RegistrationTestRequest) -> dict[str, Any]:
    return await _run_registration_test(payload, mode=payload.mode)


@api_router.post("/registration/http-risk-probe")
async def run_http_risk_probe(payload: HttpRiskProbeRequest) -> dict[str, Any]:
    settings = load_settings()
    client = OpenAIRegistrationClient(
        auth_url=settings.openai.auth_url,
        oauth_client_id=settings.openai.oauth_client_id,
        timeout=min(settings.openai.timeout_seconds, 45.0),
        proxy=settings.network.openai_proxy or settings.network.http_proxy,
    )
    result = await client.probe_authorize_challenge(
        auth_url=settings.openai.auth_url,
        authorize_url=payload.authorize_url or settings.openai.authorize_url,
    )
    return {
        "probed_at": datetime.now().isoformat(),
        **result,
    }


@api_router.get("/test/last")
async def get_last_test_run() -> dict[str, Any]:
    manager = get_test_manager()
    return await manager.get_last()


@api_router.get("/logs/files")
def list_log_files() -> dict[str, list[str]]:
    collector = LogCollector()
    return {"files": collector.list_log_files()}


@api_router.get("/logs/history")
def read_log_history(
    file: str = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    collector = LogCollector()
    try:
        items = collector.read_log_file(file, offset=offset, limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"items": items, "file": file, "offset": offset, "limit": limit}


@ws_router.websocket("/ws/test")
async def ws_test(websocket: WebSocket) -> None:
    token = (websocket.query_params.get("token") or "").strip()
    if not token:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    manager = get_test_manager()
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
