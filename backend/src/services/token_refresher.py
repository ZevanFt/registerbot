"""Background access token refresher."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog


@dataclass(frozen=True)
class TokenRefresherSettings:
    oauth_client_id: str
    oauth_client_secret: str
    token_url: str
    refresh_interval: int
    skew_seconds: int
    timeout: float
    max_retries: int
    backoff_seconds: int


class TokenRefresher:
    """Refresh expiring OpenAI access tokens in background."""

    def __init__(self, account_store: Any, registration_client: Any, settings: TokenRefresherSettings) -> None:
        self.account_store = account_store
        self.registration_client = registration_client
        self.settings = settings
        self._logger = structlog.get_logger(self.__class__.__name__)

    async def run_forever(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.settings.refresh_interval)
                await self.refresh_once()
        except asyncio.CancelledError:
            return

    async def refresh_once(self) -> None:
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(seconds=self.settings.skew_seconds)
        candidates = self._select_candidates(deadline)

        for account in candidates:
            account_id = int(account["id"])
            refresh_token = str(account.get("refresh_token") or "")
            if not refresh_token:
                continue

            self._logger.info("token_refresh_started", account_id=account_id)
            self.account_store.update_account(account_id, {"token_status": "refreshing"})

            try:
                result = await self._refresh_with_retries(refresh_token)
                expires_in = int(result["expires_in"])
                refreshed_at = datetime.now(timezone.utc)
                updates: dict[str, Any] = {
                    "openai_token": str(result["access_token"]),
                    "token_expires_at": (refreshed_at + timedelta(seconds=expires_in)).isoformat(),
                    "token_last_refreshed_at": refreshed_at.isoformat(),
                    "token_status": "valid",
                    "token_refresh_attempts": 0,
                    "token_refresh_error": None,
                }
                rotated_refresh_token = result.get("refresh_token")
                if rotated_refresh_token:
                    updates["refresh_token"] = str(rotated_refresh_token)
                self.account_store.update_account(account_id, updates)
                self._logger.info("token_refresh_success", account_id=account_id, expires_in=expires_in)
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                status = "invalid_grant" if "invalid_grant" in message else "refresh_failed"
                next_attempts = int(account.get("token_refresh_attempts") or 0) + 1
                self.account_store.update_account(
                    account_id,
                    {
                        "token_status": status,
                        "token_refresh_attempts": next_attempts,
                        "token_refresh_error": message,
                    },
                )
                self._logger.warning(
                    "token_refresh_failed",
                    account_id=account_id,
                    token_status=status,
                    error=message,
                    attempts=next_attempts,
                )

    def _select_candidates(self, deadline: datetime) -> list[dict[str, Any]]:
        accounts = self.account_store.list_accounts()
        selected: list[dict[str, Any]] = []
        for account in accounts:
            refresh_token = str(account.get("refresh_token") or "")
            if not refresh_token:
                continue

            token_status = str(account.get("token_status") or "unknown")
            if token_status in {"invalid_grant", "refreshing"}:
                continue

            expires_at = self._parse_iso(account.get("token_expires_at"))
            should_refresh_by_expire = expires_at is not None and expires_at <= deadline
            should_refresh_by_status = token_status in {"expired", "refresh_failed", "expiring"}
            if should_refresh_by_expire or should_refresh_by_status:
                selected.append(account)

        return selected

    async def _refresh_with_retries(self, refresh_token: str) -> dict[str, Any]:
        max_attempts = max(1, int(self.settings.max_retries))
        for attempt in range(1, max_attempts + 1):
            try:
                return await asyncio.wait_for(
                    self.registration_client.refresh_access_token(
                        refresh_token=refresh_token,
                        client_id=self.settings.oauth_client_id,
                        client_secret=self.settings.oauth_client_secret,
                        token_url=self.settings.token_url,
                    ),
                    timeout=self.settings.timeout,
                )
            except Exception as exc:  # noqa: BLE001
                if "invalid_grant" in str(exc):
                    raise
                if attempt >= max_attempts:
                    raise
                await asyncio.sleep(self.settings.backoff_seconds)
        raise RuntimeError("token_refresh_failed: exhausted retries")

    def _parse_iso(self, value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
