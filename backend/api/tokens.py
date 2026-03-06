"""Token management API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.config.settings import load_settings
from src.middleware.auth import require_operator_permission
from src.storage.token_store import TokenStore

router = APIRouter(
    prefix="/api/tokens",
    tags=["tokens"],
    dependencies=[Depends(require_operator_permission)],
)


class TokenCreateRequest(BaseModel):
    """Request model for creating a token."""

    name: str = Field(min_length=1)


def _build_store() -> TokenStore:
    settings = load_settings()
    return TokenStore(settings.storage.tokens_db_path)


@router.get("")
def list_tokens(reveal: bool = False) -> list[dict]:
    store = _build_store()
    tokens = store.list_tokens()
    if not reveal:
        for token in tokens:
            key = token.get("key", "")
            token["key"] = key[:10] + "****" if len(key) > 10 else key
    return tokens


@router.post("", status_code=status.HTTP_201_CREATED)
def create_token(payload: TokenCreateRequest) -> dict:
    store = _build_store()
    return store.create_token(payload.name)


@router.delete("/{token_id}")
def revoke_token(token_id: int) -> dict[str, str]:
    store = _build_store()
    if not store.revoke_token(token_id):
        raise HTTPException(status_code=404, detail="Token not found")
    return {"status": "revoked"}


@router.delete("/{token_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
def delete_token_permanent(token_id: int) -> None:
    store = _build_store()
    if not store.delete_token(token_id):
        raise HTTPException(status_code=404, detail="Token not found")
