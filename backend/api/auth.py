"""Admin authentication API routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.config.settings import load_settings
from src.middleware.auth import AdminContext, require_admin_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    token: str
    username: str


class MeResponse(BaseModel):
    username: str


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    settings = load_settings()
    if payload.username != settings.admin.username or payload.password != settings.admin.password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    expire_at = datetime.now(tz=UTC) + timedelta(hours=settings.admin.jwt_expire_hours)
    token = jwt.encode(
        {"sub": payload.username, "exp": expire_at},
        settings.admin.jwt_secret,
        algorithm="HS256",
    )
    return LoginResponse(token=token, username=payload.username)


@router.get("/me", response_model=MeResponse)
def me(ctx: AdminContext = Depends(require_admin_token)) -> MeResponse:
    return MeResponse(username=ctx.username)
