"""Authentication dependencies and OpenAI-compatible error helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import jwt
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel

from src.config.settings import load_settings
from src.storage.token_store import TokenStore


class TokenContext(BaseModel):
    """Resolved token context from bearer auth."""

    token_id: int
    key: str
    name: str


class AdminContext(BaseModel):
    """Resolved admin context from JWT auth."""

    username: str
    permission: str = "admin"


class OpenAIProxyException(Exception):
    """Error that should be rendered in OpenAI error JSON format."""

    def __init__(
        self,
        status_code: int,
        message: str,
        error_type: str,
        code: str,
        param: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_type = error_type
        self.code = code
        self.param = param


def build_openai_error(message: str, error_type: str, code: str, param: str | None = None) -> dict:
    return {
        "error": {
            "message": message,
            "type": error_type,
            "param": param,
            "code": code,
        }
    }


def _build_store() -> TokenStore:
    settings = load_settings()
    return TokenStore(settings.storage.tokens_db_path)


async def require_admin_token(request: Request) -> AdminContext:
    """Validate admin JWT from Authorization header."""

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    settings = load_settings()
    try:
        payload = jwt.decode(token, settings.admin.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Unauthorized") from None

    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        if datetime.fromtimestamp(exp, tz=UTC) <= datetime.now(tz=UTC):
            raise HTTPException(status_code=401, detail="Unauthorized")

    username = payload.get("sub")
    if not isinstance(username, str) or not username:
        raise HTTPException(status_code=401, detail="Unauthorized")
    permission = payload.get("permission")
    if not isinstance(permission, str) or not permission:
        permission = "admin"

    return AdminContext(username=username, permission=permission)


_PERMISSION_LEVELS = {
    "viewer": 1,
    "operator": 2,
    "admin": 3,
}


def _has_permission(actual: str, required: str) -> bool:
    return _PERMISSION_LEVELS.get(actual, 0) >= _PERMISSION_LEVELS.get(required, 0)


async def require_viewer_permission(ctx: AdminContext = Depends(require_admin_token)) -> AdminContext:
    if not _has_permission(ctx.permission, "viewer"):
        raise HTTPException(status_code=403, detail="Insufficient permission")
    return ctx


async def require_operator_permission(ctx: AdminContext = Depends(require_admin_token)) -> AdminContext:
    if not _has_permission(ctx.permission, "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permission")
    return ctx


async def require_admin_permission(ctx: AdminContext = Depends(require_admin_token)) -> AdminContext:
    if not _has_permission(ctx.permission, "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permission")
    return ctx


async def require_bearer_token(request: Request) -> TokenContext:
    """Validate bearer token from Authorization header."""

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise OpenAIProxyException(
            status_code=401,
            message="Missing bearer token",
            error_type="invalid_request_error",
            code="unauthorized",
        )

    key = authorization.removeprefix("Bearer ").strip()
    if not key:
        raise OpenAIProxyException(
            status_code=401,
            message="Missing bearer token",
            error_type="invalid_request_error",
            code="unauthorized",
        )

    token = _build_store().get_active_token_by_key(key)
    if token is None:
        raise OpenAIProxyException(
            status_code=401,
            message="Invalid API key provided",
            error_type="invalid_request_error",
            code="invalid_api_key",
        )

    return TokenContext(token_id=token["id"], key=token["key"], name=token["name"])
