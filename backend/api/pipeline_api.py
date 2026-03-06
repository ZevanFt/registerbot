"""Registration pipeline API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.ws_pipeline import get_pipeline_event_hub
from src.config.settings import load_settings
from src.integrations.talentmail import TalentMailClient
from src.middleware.auth import require_operator_permission
from src.services.registration_service import RegistrationService
from src.storage.account_store import AccountStore

router = APIRouter(
    prefix="/api/pipeline",
    tags=["pipeline"],
    dependencies=[Depends(require_operator_permission)],
)
_registration_service: RegistrationService | None = None


class RegisterRequest(BaseModel):
    email: str | None = None
    password: str | None = None


def _build_service() -> RegistrationService:
    global _registration_service
    settings = load_settings()
    if _registration_service is None:
        account_store = AccountStore(settings.storage.db_path, settings.storage.encryption_key)
        _registration_service = RegistrationService(settings=settings, account_store=account_store)
    return _registration_service


@router.post("/register")
async def register_account(payload: RegisterRequest) -> dict[str, Any]:
    settings = load_settings()
    email = (payload.email or "").strip()
    if not email:
        async with TalentMailClient(
            base_url=settings.talentmail.base_url,
            email=settings.talentmail.email,
            password=settings.talentmail.password,
            proxy=settings.network.talentmail_proxy or settings.network.http_proxy,
        ) as mail_client:
            mailbox = await mail_client.create_temp_email()
        email = str(mailbox.get("email") or "")
        if not email:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create temp email")

    password = payload.password or settings.openai.default_password
    if not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required when openai.default_password is empty",
        )

    event_hub = get_pipeline_event_hub()
    result = await _build_service().register_account(email=email, password=password, event_callback=event_hub.emit)
    if not result.get("success", False):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)
    return result


@router.get("/status")
def get_pipeline_status() -> dict[str, Any]:
    return _build_service().get_status()
