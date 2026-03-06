"""Dashboard and account management API routes."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import secrets
import sys
import time
from collections import Counter
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.config.settings import load_settings
from src.integrations.openai_api import OpenAIChatClient
from src.middleware.auth import AdminContext, require_admin_token
from src.services.account_pool import AccountPool, NoAvailableAccountError
from src.storage.account_store import AccountStore
from src.storage.stats_store import StatsStore
from src.storage.user_store import UserStore

router = APIRouter(prefix="/api", tags=["dashboard"])
_SERVICE_STARTED_AT = time.time()
_CHAT2API_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4",
    "gpt-3.5-turbo",
    "o1-preview",
    "o1-mini",
    "o3-mini",
    "gpt-5.3-codex",
    "gpt-5-codex-mini",
    "gpt-5.2-codex",
    "gpt-5.1-codex",
    "gpt-5.1-codex-max",
    "gpt-5-codex",
]


class AccountCreateRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)
    plan: str = "free"
    status: str = "pending"
    phone: str | None = None
    openai_token: str | None = None


class AccountStatusPatchRequest(BaseModel):
    status: str = Field(min_length=1)


class AccountImportItem(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)
    plan: str = "free"
    status: str = "active"
    phone: str | None = None
    openai_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: str | None = None
    token_last_refreshed_at: str | None = None
    token_status: str = "unknown"
    token_refresh_error: str | None = None
    token_refresh_attempts: int = 0


class AccountImportRequest(BaseModel):
    conflict_strategy: str = "skip"
    accounts: list[AccountImportItem] = Field(default_factory=list)


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3)
    password: str = Field(min_length=6)
    permission: str = Field(default="operator", min_length=3)
    email: str | None = None
    is_active: bool = True


class UserPatchRequest(BaseModel):
    permission: str | None = None
    email: str | None = None
    is_active: bool | None = None


class UserResetPasswordRequest(BaseModel):
    new_password: str | None = None


def _build_store() -> AccountStore:
    settings = load_settings()
    return AccountStore(settings.storage.db_path, settings.storage.encryption_key)


def _build_stats_store() -> StatsStore:
    settings = load_settings()
    return StatsStore(settings.storage.stats_db_path)


def _build_user_store() -> UserStore:
    settings = load_settings()
    store = UserStore(settings.storage.db_path)
    store.ensure_admin_user(settings.admin.username, settings.admin.password)
    return store


def _sanitize_account(account: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": account["id"],
        "email": account["email"],
        "plan": account["plan"],
        "status": account["status"],
        "runtime_status": account.get("runtime_status"),
        "token_status": account.get("token_status"),
        "consecutive_failures": int(account.get("consecutive_failures") or 0),
        "last_failure_reason": account.get("last_failure_reason"),
        "created_at": account["created_at"],
        "updated_at": account["updated_at"],
    }


def _sanitize_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(user["id"]),
        "username": str(user["username"]),
        "email": user.get("email"),
        "permission": str(user.get("permission") or "operator"),
        "is_active": bool(int(user.get("is_active") or 0)),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at"),
        "last_login_at": user.get("last_login_at"),
    }


def _assert_admin_permission(ctx: AdminContext) -> None:
    if ctx.permission != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permission required")


def _get_account_with_health(store: AccountStore, account_id: int) -> dict[str, Any] | None:
    for item in store.list_accounts_with_health():
        if int(item.get("id", -1)) == account_id:
            return item
    return None


def _find_account_by_email(store: AccountStore, email: str) -> dict[str, Any] | None:
    target = email.strip().lower()
    for item in store.list_accounts_with_health():
        if str(item.get("email", "")).strip().lower() == target:
            return item
    return None


def _is_chat2api_mode(base_url: str) -> bool:
    return "localhost" in base_url or "127.0.0.1" in base_url


def _build_chat_client(timeout_seconds: float = 8.0) -> OpenAIChatClient:
    settings = load_settings()
    base_url = settings.openai.base_url
    if _is_chat2api_mode(base_url):
        proxy = ""
    else:
        proxy = settings.network.openai_proxy or settings.network.http_proxy
    return OpenAIChatClient(
        base_url=base_url,
        timeout=min(settings.openai.timeout_seconds, timeout_seconds),
        stream_timeout=min(settings.openai.stream_timeout_seconds, timeout_seconds),
        proxy=proxy,
    )


async def _load_available_models(store: AccountStore) -> tuple[list[dict[str, str]], bool]:
    settings = load_settings()
    if _is_chat2api_mode(settings.openai.base_url):
        return [{"id": model_id, "name": model_id} for model_id in _CHAT2API_MODELS], True

    pool = AccountPool(
        account_store=store,
        cooldown_seconds=settings.proxy.cooldown_seconds,
        failure_threshold=settings.proxy.failure_threshold,
    )
    try:
        account = pool.acquire_account()
    except NoAvailableAccountError:
        return [], False

    try:
        payload = await _build_chat_client().list_models(str(account["openai_token"]))
        raw_models = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(raw_models, list):
            return [], False
        models: list[dict[str, str]] = []
        for item in raw_models:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id", "")).strip()
            if not model_id:
                continue
            models.append({"id": model_id, "name": model_id})
        pool.mark_success(int(account["id"]))
        return models, True
    except (httpx.RequestError, httpx.HTTPStatusError, httpx.TimeoutException):
        pool.mark_failure(int(account["id"]), "list_models_failed")
        return [], False


def _fallback_models_from_usage(stats_store: StatsStore) -> list[dict[str, str]]:
    distribution = stats_store.get_model_distribution()
    models: list[dict[str, str]] = []
    for item in distribution:
        model_id = str(item.get("model", "")).strip()
        if not model_id:
            continue
        models.append({"id": model_id, "name": model_id})
    return models


@router.get("/dashboard/stats")
def get_dashboard_stats() -> dict[str, Any]:
    store = _build_store()
    stats_store = _build_stats_store()
    accounts = store.list_accounts()
    statuses = Counter(str(item.get("status", "")) for item in accounts)
    today_summary = stats_store.get_today_summary()
    current_rpm = stats_store.get_recent_rpm()
    current_tpm = stats_store.get_recent_tpm()
    success_rate = stats_store.get_today_success_rate()
    discovered_models, upstream_ok = asyncio.run(_load_available_models(store))
    models = discovered_models or _fallback_models_from_usage(stats_store)
    settings = load_settings()
    chat2api_mode = _is_chat2api_mode(settings.openai.base_url)
    return {
        "accounts": {
            "total": len(accounts),
            "active": statuses.get("active", 0),
            "cooling": statuses.get("cooling", 0),
            "banned": statuses.get("banned", 0),
            "expired": statuses.get("expired", 0),
            "abandoned": statuses.get("abandoned", 0),
        },
        "usage": {
            "today_requests": int(today_summary.get("total_requests", 0)),
            "today_tokens": int(today_summary.get("total_tokens", 0)),
            "current_rpm": current_rpm,
            "success_rate": success_rate,
            "current_tpm": current_tpm,
        },
        "models": models,
        "service": {
            "uptime_seconds": int(time.time() - _SERVICE_STARTED_AT),
            "schedule_mode": "round-robin",
            "version": "1.0.0",
            "python_version": sys.version.split()[0],
            "openai_base_url": settings.openai.base_url,
            "chat2api_mode": chat2api_mode,
            "upstream_status": "reachable" if upstream_ok else "unreachable",
        },
    }


@router.get("/accounts")
def list_accounts() -> list[dict[str, Any]]:
    store = _build_store()
    return [_sanitize_account(item) for item in store.list_accounts_with_health()]


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreateRequest) -> dict[str, Any]:
    store = _build_store()
    account_id = store.save_account(payload.model_dump())
    account = _get_account_with_health(store, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Account create failed")
    return _sanitize_account(account)


@router.patch("/accounts/{account_id}")
def patch_account_status(account_id: int, payload: AccountStatusPatchRequest) -> dict[str, Any]:
    store = _build_store()
    updated = store.update_account(account_id, {"status": payload.status})
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    account = _get_account_with_health(store, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return _sanitize_account(account)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int) -> None:
    store = _build_store()
    deleted = store.delete_account(account_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")


@router.get("/accounts/{account_id}/password/reveal")
def reveal_account_password(account_id: int) -> dict[str, Any]:
    store = _build_store()
    account = store.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return {
        "id": account["id"],
        "email": account["email"],
        "password": account["password"],
    }


@router.get("/accounts/export")
def export_accounts(ids: str | None = None) -> dict[str, Any]:
    store = _build_store()
    all_accounts = store.list_accounts_with_health()
    accounts_map = {int(item["id"]): item for item in all_accounts}

    selected_ids: set[int] | None = None
    if ids:
        selected_ids = set()
        for part in ids.split(","):
            text = part.strip()
            if not text:
                continue
            try:
                selected_ids.add(int(text))
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid id: {text}") from exc

    exported: list[dict[str, Any]] = []
    for item in store.list_accounts():
        account_id = int(item["id"])
        if selected_ids is not None and account_id not in selected_ids:
            continue
        health = accounts_map.get(account_id, {})
        exported.append(
            {
                "id": account_id,
                "email": item["email"],
                "password": item["password"],
                "plan": item["plan"],
                "status": item["status"],
                "phone": item.get("phone"),
                "openai_token": item.get("openai_token"),
                "refresh_token": item.get("refresh_token"),
                "token_expires_at": item.get("token_expires_at"),
                "token_last_refreshed_at": item.get("token_last_refreshed_at"),
                "token_status": item.get("token_status"),
                "token_refresh_error": item.get("token_refresh_error"),
                "token_refresh_attempts": int(item.get("token_refresh_attempts") or 0),
                "runtime_status": health.get("runtime_status"),
                "consecutive_failures": int(health.get("consecutive_failures") or 0),
                "last_failure_reason": health.get("last_failure_reason"),
            }
        )

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "count": len(exported),
        "accounts": exported,
    }


@router.post("/accounts/import")
def import_accounts(payload: AccountImportRequest) -> dict[str, Any]:
    store = _build_store()
    strategy = payload.conflict_strategy.strip().lower()
    if strategy not in {"skip", "overwrite"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="conflict_strategy must be skip or overwrite",
        )

    imported = 0
    updated = 0
    skipped = 0
    failed = 0
    errors: list[dict[str, Any]] = []

    for item in payload.accounts:
        email = item.email.strip()
        if not email:
            failed += 1
            errors.append({"email": item.email, "error": "email is required"})
            continue
        try:
            exists = _find_account_by_email(store, email)
            account_payload = item.model_dump()
            if exists is None:
                store.save_account(account_payload)
                imported += 1
                continue

            if strategy == "skip":
                skipped += 1
                continue

            account_id = int(exists["id"])
            store.update_account(
                account_id,
                {
                    "email": account_payload["email"],
                    "password": account_payload["password"],
                    "plan": account_payload["plan"],
                    "status": account_payload["status"],
                    "phone": account_payload.get("phone"),
                    "openai_token": account_payload.get("openai_token"),
                    "refresh_token": account_payload.get("refresh_token"),
                    "token_expires_at": account_payload.get("token_expires_at"),
                    "token_last_refreshed_at": account_payload.get("token_last_refreshed_at"),
                    "token_status": account_payload.get("token_status"),
                    "token_refresh_error": account_payload.get("token_refresh_error"),
                    "token_refresh_attempts": int(account_payload.get("token_refresh_attempts") or 0),
                },
            )
            updated += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            errors.append({"email": email, "error": str(exc)})

    return {
        "total": len(payload.accounts),
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
    }


@router.get("/users")
def list_users(ctx: AdminContext = Depends(require_admin_token)) -> list[dict[str, Any]]:
    _assert_admin_permission(ctx)
    store = _build_user_store()
    return [_sanitize_user(item) for item in store.list_users()]


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreateRequest, ctx: AdminContext = Depends(require_admin_token)) -> dict[str, Any]:
    _assert_admin_permission(ctx)
    permission = payload.permission.strip().lower()
    if permission not in {"admin", "operator", "viewer"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="permission must be admin/operator/viewer")

    store = _build_user_store()
    try:
        user_id = store.create_user(
            username=payload.username,
            password=payload.password,
            permission=permission,
            email=payload.email,
            is_active=payload.is_active,
        )
    except Exception as exc:  # noqa: BLE001
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username or email already exists") from exc
        raise
    created = store.get_user(user_id)
    if created is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User create failed")
    return _sanitize_user(created)


@router.patch("/users/{user_id}")
def patch_user(
    user_id: int,
    payload: UserPatchRequest,
    ctx: AdminContext = Depends(require_admin_token),
) -> dict[str, Any]:
    _assert_admin_permission(ctx)
    permission = payload.permission.strip().lower() if payload.permission is not None else None
    if permission is not None and permission not in {"admin", "operator", "viewer"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="permission must be admin/operator/viewer")

    store = _build_user_store()
    try:
        updated = store.update_user(
            user_id,
            permission=permission,
            email=payload.email,
            is_active=payload.is_active,
        )
    except Exception as exc:  # noqa: BLE001
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already exists") from exc
        raise
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user = store.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _sanitize_user(user)


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    payload: UserResetPasswordRequest,
    ctx: AdminContext = Depends(require_admin_token),
) -> dict[str, Any]:
    _assert_admin_permission(ctx)
    next_password = payload.new_password or f"Tmp-{secrets.token_urlsafe(10)}"
    if len(next_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="password too short")

    store = _build_user_store()
    updated = store.reset_password(user_id, next_password)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user = store.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        "id": int(user["id"]),
        "username": str(user["username"]),
        "permission": str(user.get("permission") or "operator"),
        "new_password": next_password,
    }
