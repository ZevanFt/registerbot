"""Configuration read and update API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.config.settings import load_settings, save_settings
from src.middleware.auth import require_admin_permission

router = APIRouter(
    prefix="/api/config",
    tags=["config"],
    dependencies=[Depends(require_admin_permission)],
)


@router.get("")
def get_config() -> dict[str, Any]:
    settings = load_settings()
    payload = settings.model_dump()
    if payload.get("talentmail", {}).get("password"):
        payload["talentmail"]["password"] = "***"
    if payload.get("storage", {}).get("encryption_key"):
        payload["storage"]["encryption_key"] = "***"
    if payload.get("admin", {}).get("password"):
        payload["admin"]["password"] = "***"
    if payload.get("admin", {}).get("jwt_secret"):
        payload["admin"]["jwt_secret"] = "***"
    return payload


class ConfigUpdateRequest(BaseModel):
    """Request model for partial config updates."""

    talentmail: dict | None = None
    openai: dict | None = None
    registration: dict | None = None
    proxy: dict | None = None
    network: dict | None = None
    storage: dict | None = None
    logging: dict | None = None
    admin: dict | None = None


@router.put("")
def update_config(payload: ConfigUpdateRequest) -> dict[str, Any]:
    current = load_settings().model_dump()
    updates = payload.model_dump(exclude_none=True)
    for section, values in updates.items():
        if section not in current:
            continue
        for key, value in values.items():
            if value == "***":
                continue
            current[section][key] = value
    save_settings(current)
    return get_config()
