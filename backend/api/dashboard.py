"""Dashboard and account management API routes."""

from __future__ import annotations

import sys
import time
from collections import Counter
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.config.settings import load_settings
from src.storage.account_store import AccountStore

router = APIRouter(prefix="/api", tags=["dashboard"])
_SERVICE_STARTED_AT = time.time()


class AccountCreateRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)
    plan: str = "free"
    status: str = "pending"
    phone: str | None = None
    openai_token: str | None = None


class AccountStatusPatchRequest(BaseModel):
    status: str = Field(min_length=1)


def _build_store() -> AccountStore:
    settings = load_settings()
    return AccountStore(settings.storage.db_path, settings.storage.encryption_key)


def _sanitize_account(account: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": account["id"],
        "email": account["email"],
        "plan": account["plan"],
        "status": account["status"],
        "created_at": account["created_at"],
        "updated_at": account["updated_at"],
    }


@router.get("/dashboard/stats")
def get_dashboard_stats() -> dict[str, Any]:
    store = _build_store()
    accounts = store.list_accounts()
    statuses = Counter(str(item.get("status", "")) for item in accounts)
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
            "today_requests": 0,
            "today_tokens": 0,
            "current_rpm": 0,
        },
        "models": [
            {"id": "codex/gpt-5-codex-mini", "name": "GPT-5 Codex Mini"},
            {"id": "codex/gpt-5-codex", "name": "GPT-5 Codex"},
            {"id": "codex/gpt-5.1-codex", "name": "GPT-5.1 Codex"},
            {"id": "codex/gpt-5.1-codex-max", "name": "GPT-5.1 Codex Max"},
        ],
        "service": {
            "uptime_seconds": int(time.time() - _SERVICE_STARTED_AT),
            "schedule_mode": "round-robin",
            "version": "1.0.0",
            "python_version": sys.version.split()[0],
        },
    }


@router.get("/accounts")
def list_accounts() -> list[dict[str, Any]]:
    store = _build_store()
    return [_sanitize_account(item) for item in store.list_accounts()]


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreateRequest) -> dict[str, Any]:
    store = _build_store()
    account_id = store.save_account(payload.model_dump())
    account = store.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Account create failed")
    return _sanitize_account(account)


@router.patch("/accounts/{account_id}")
def patch_account_status(account_id: int, payload: AccountStatusPatchRequest) -> dict[str, Any]:
    store = _build_store()
    updated = store.update_account(account_id, {"status": payload.status})
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    account = store.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return _sanitize_account(account)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int) -> None:
    store = _build_store()
    deleted = store.delete_account(account_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
