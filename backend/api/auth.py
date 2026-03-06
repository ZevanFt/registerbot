"""Admin authentication API routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.config.settings import load_settings
from src.middleware.auth import AdminContext, require_admin_token
from src.storage.user_store import UserStore

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    token: str
    username: str
    permission: str


class MeResponse(BaseModel):
    username: str
    permission: str


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    settings = load_settings()
    store = UserStore(settings.storage.db_path)
    store.ensure_admin_user(settings.admin.username, settings.admin.password)
    user = store.verify_credentials(payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    permission = str(user.get("permission") or "admin")
    username = str(user.get("username") or payload.username)
    expire_at = datetime.now(tz=UTC) + timedelta(hours=settings.admin.jwt_expire_hours)
    token = jwt.encode(
        {"sub": username, "permission": permission, "exp": expire_at},
        settings.admin.jwt_secret,
        algorithm="HS256",
    )
    return LoginResponse(token=token, username=username, permission=permission)


@router.get("/me", response_model=MeResponse)
def me(ctx: AdminContext = Depends(require_admin_token)) -> MeResponse:
    return MeResponse(username=ctx.username, permission=ctx.permission)
