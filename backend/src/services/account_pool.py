"""Round-robin account pool backed by persistent account health state."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog


class NoAvailableAccountError(RuntimeError):
    """Raised when no active account can be selected."""


class AccountPool:
    """Pick active upstream accounts with round-robin and persistent health rules."""

    def __init__(self, account_store: Any, cooldown_seconds: int = 60, failure_threshold: int = 3) -> None:
        self.account_store = account_store
        self.cooldown_seconds = cooldown_seconds
        self.failure_threshold = failure_threshold
        self._next_index = 0
        self._lock = threading.Lock()
        self._logger = structlog.get_logger(self.__class__.__name__)

    def _recover_cooling(self, account: dict[str, Any]) -> bool:
        """Check if a cooling account's cooldown has expired and recover it inline."""
        cooldown_raw = account.get("cooldown_until")
        if not cooldown_raw or not isinstance(cooldown_raw, str):
            return False
        try:
            cooldown_until = datetime.fromisoformat(cooldown_raw)
            if cooldown_until.tzinfo is None:
                cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)
        except ValueError:
            return False
        if cooldown_until <= datetime.now(timezone.utc):
            account_id = int(account["id"])
            self.account_store.ensure_health_record(account_id)
            self.account_store.update_health(
                account_id,
                runtime_status="active",
                consecutive_failures=0,
                cooldown_until=None,
            )
            self._logger.info("account_recovered_inline", account_id=account_id)
            return True
        return False

    def acquire_account(self) -> dict[str, Any]:
        with self._lock:
            all_accounts = self.account_store.list_accounts_with_health()

            # Inline-recover cooling accounts whose cooldown has expired
            for account in all_accounts:
                if account.get("runtime_status") == "cooling":
                    if self._recover_cooling(account):
                        account["runtime_status"] = "active"

            accounts = [
                account
                for account in all_accounts
                if account.get("status") == "active"
                and account.get("runtime_status") == "active"
                and account.get("openai_token")
                and str(account.get("token_status") or "unknown")
                not in {"expired", "invalid_grant", "refreshing", "refresh_failed"}
            ]

            if not accounts:
                raise NoAvailableAccountError("no active account available")

            if self._next_index >= len(accounts):
                self._next_index = 0
            account = accounts[self._next_index]
            self._next_index = (self._next_index + 1) % len(accounts)
            return account

    def mark_success(self, account_id: int) -> None:
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            self.account_store.ensure_health_record(account_id)
            self.account_store.update_health(
                account_id,
                runtime_status="active",
                consecutive_failures=0,
                cooldown_until=None,
                last_success_at=now,
            )

    def mark_failure(self, account_id: int, reason: str) -> None:
        with self._lock:
            now = datetime.now(timezone.utc)
            self.account_store.ensure_health_record(account_id)
            health = self.account_store.get_health(account_id) or {}
            fail_count = int(health.get("consecutive_failures", 0)) + 1
            total_failures = int(health.get("total_failures", 0)) + 1
            runtime_status = "banned" if fail_count >= self.failure_threshold else "cooling"
            cooldown_until: str | None = None
            if runtime_status == "cooling":
                cooldown_until = (now + timedelta(seconds=self.cooldown_seconds)).isoformat()
            self.account_store.update_health(
                account_id,
                runtime_status=runtime_status,
                consecutive_failures=fail_count,
                total_failures=total_failures,
                cooldown_until=cooldown_until,
                last_failure_at=now.isoformat(),
                last_failure_reason=reason,
            )

        self._logger.warning(
            "account_marked_failure",
            account_id=account_id,
            reason=reason,
            fail_count=fail_count,
            runtime_status=runtime_status,
            cooldown_until=cooldown_until,
        )
