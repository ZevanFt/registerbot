"""Background account health checker."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog


class HealthChecker:
    """Periodically probe upstream account health and persist runtime status."""

    def __init__(
        self,
        account_store: Any,
        chat_client: Any,
        interval: int = 30,
        cooldown_seconds: int = 60,
        failure_threshold: int = 3,
        skip_probe: bool = False,
    ) -> None:
        self.account_store = account_store
        self.chat_client = chat_client
        self.interval = interval
        self.cooldown_seconds = cooldown_seconds
        self.failure_threshold = failure_threshold
        self.skip_probe = skip_probe
        self._logger = structlog.get_logger(self.__class__.__name__)

    async def run_forever(self) -> None:
        while True:
            await self.check_once()
            await asyncio.sleep(self.interval)

    async def check_once(self) -> None:
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        self._logger.info("health_check_started", timestamp=now_iso)

        accounts = self.account_store.list_accounts_with_health()
        for account in accounts:
            account_id = int(account["id"])
            self.account_store.ensure_health_record(account_id)

            runtime_status = str(account.get("runtime_status", "active"))
            cooldown_until_raw = account.get("cooldown_until")
            cooldown_until = self._parse_iso(cooldown_until_raw)
            if runtime_status in {"cooling", "usage_limited"} and cooldown_until is not None and cooldown_until <= now:
                self.account_store.update_health(
                    account_id,
                    runtime_status="active",
                    consecutive_failures=0,
                    cooldown_until=None,
                    last_check_at=now_iso,
                )
                self._logger.info("account_recovered", account_id=account_id, from_status=runtime_status)

        refreshed = self.account_store.list_accounts_with_health()
        active_accounts = [
            account
            for account in refreshed
            if account.get("runtime_status") == "active" and account.get("openai_token")
            and str(account.get("token_status") or "unknown") in {"valid", "expiring", "unknown"}
        ]

        if self.skip_probe:
            self._logger.debug("health_check_probe_skipped", reason="chat2api_mode")
            return

        for account in active_accounts:
            account_id = int(account["id"])
            token = str(account["openai_token"])
            try:
                await self.chat_client.list_models(token)
                self.account_store.update_health(
                    account_id,
                    last_check_at=now_iso,
                    last_success_at=now_iso,
                    consecutive_failures=0,
                    runtime_status="active",
                    cooldown_until=None,
                )
                self._logger.info("health_check_result", account_id=account_id, result="success")
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {401, 403}:
                    self.account_store.update_account(account_id, {"token_status": "expired"})
                    self._logger.warning(
                        "token_expired_detected",
                        account_id=account_id,
                        status_code=exc.response.status_code,
                    )
                    continue
                fail_count = int(account.get("consecutive_failures", 0)) + 1
                total_failures = int(account.get("total_failures", 0)) + 1
                runtime_status = "banned" if fail_count >= self.failure_threshold else "cooling"
                cooldown_until: str | None = None
                if runtime_status == "cooling":
                    cooldown_until = (now + timedelta(seconds=self.cooldown_seconds)).isoformat()
                self.account_store.update_health(
                    account_id,
                    last_check_at=now_iso,
                    last_failure_at=now_iso,
                    last_failure_reason=str(exc),
                    consecutive_failures=fail_count,
                    total_failures=total_failures,
                    runtime_status=runtime_status,
                    cooldown_until=cooldown_until,
                )
                self._logger.warning(
                    "health_check_result",
                    account_id=account_id,
                    result="failure",
                    reason=str(exc),
                    fail_count=fail_count,
                )
                if runtime_status == "banned":
                    self._logger.warning("account_banned", account_id=account_id, fail_count=fail_count)
            except Exception as exc:  # noqa: BLE001
                fail_count = int(account.get("consecutive_failures", 0)) + 1
                total_failures = int(account.get("total_failures", 0)) + 1
                runtime_status = "banned" if fail_count >= self.failure_threshold else "cooling"
                cooldown_until: str | None = None
                if runtime_status == "cooling":
                    cooldown_until = (now + timedelta(seconds=self.cooldown_seconds)).isoformat()
                self.account_store.update_health(
                    account_id,
                    last_check_at=now_iso,
                    last_failure_at=now_iso,
                    last_failure_reason=str(exc),
                    consecutive_failures=fail_count,
                    total_failures=total_failures,
                    runtime_status=runtime_status,
                    cooldown_until=cooldown_until,
                )
                self._logger.warning(
                    "health_check_result",
                    account_id=account_id,
                    result="failure",
                    reason=str(exc),
                    fail_count=fail_count,
                )
                if runtime_status == "banned":
                    self._logger.warning("account_banned", account_id=account_id, fail_count=fail_count)

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
