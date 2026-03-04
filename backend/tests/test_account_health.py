"""Tests for account health persistence and account pool behavior."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from src.services.account_pool import AccountPool, NoAvailableAccountError
from src.storage.account_store import AccountStore


class AccountHealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.store = AccountStore(f"{self._tmp_dir.name}/accounts.db", "test-key-1234567890")

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def _create_active_account(self, email: str = "a@example.com", token: str = "tok-1") -> int:
        return self.store.save_account(
            {
                "email": email,
                "password": "secret",
                "status": "active",
                "openai_token": token,
                "plan": "free",
            }
        )

    def test_health_record_created_with_account(self) -> None:
        account_id = self._create_active_account()

        health = self.store.get_health(account_id)
        self.assertIsNotNone(health)
        assert health is not None
        self.assertEqual(health["runtime_status"], "active")
        self.assertEqual(health["consecutive_failures"], 0)
        self.assertEqual(health["total_failures"], 0)

    def test_mark_failure_persists_to_db(self) -> None:
        account_id = self._create_active_account()
        pool = AccountPool(self.store, cooldown_seconds=60, failure_threshold=3)

        pool.mark_failure(account_id, "timeout")

        reloaded_pool = AccountPool(self.store, cooldown_seconds=60, failure_threshold=3)
        with self.assertRaises(NoAvailableAccountError):
            reloaded_pool.acquire_account()

    def test_cooling_account_not_acquired(self) -> None:
        account_a = self._create_active_account("a@example.com", "tok-a")
        account_b = self._create_active_account("b@example.com", "tok-b")
        pool = AccountPool(self.store, cooldown_seconds=60, failure_threshold=3)

        pool.mark_failure(account_a, "status_429")
        selected = pool.acquire_account()

        self.assertEqual(selected["id"], account_b)

    def test_banned_after_threshold(self) -> None:
        account_id = self._create_active_account()
        pool = AccountPool(self.store, cooldown_seconds=60, failure_threshold=3)

        pool.mark_failure(account_id, "e1")
        pool.mark_failure(account_id, "e2")
        pool.mark_failure(account_id, "e3")

        health = self.store.get_health(account_id)
        self.assertIsNotNone(health)
        assert health is not None
        self.assertEqual(health["runtime_status"], "banned")
        self.assertEqual(health["consecutive_failures"], 3)


    def test_mark_usage_limited(self) -> None:
        account_id = self._create_active_account()
        pool = AccountPool(self.store, cooldown_seconds=60, failure_threshold=3)

        pool.mark_usage_limited(account_id)

        health = self.store.get_health(account_id)
        self.assertIsNotNone(health)
        assert health is not None
        self.assertEqual(health["runtime_status"], "usage_limited")
        self.assertIsNotNone(health["cooldown_until"])
        self.assertEqual(health["last_failure_reason"], "daily_quota_exhausted")

    def test_usage_limited_account_not_acquired(self) -> None:
        account_a = self._create_active_account("a@example.com", "tok-a")
        account_b = self._create_active_account("b@example.com", "tok-b")
        pool = AccountPool(self.store, cooldown_seconds=60, failure_threshold=3)

        pool.mark_usage_limited(account_a)
        selected = pool.acquire_account()

        self.assertEqual(selected["id"], account_b)

    def test_usage_limited_recovers_after_cooldown(self) -> None:
        account_id = self._create_active_account()
        pool = AccountPool(self.store, cooldown_seconds=60, failure_threshold=3)

        # Set cooldown to the past so it recovers inline
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self.store.update_health(
            account_id,
            runtime_status="usage_limited",
            cooldown_until=past,
            last_failure_reason="daily_quota_exhausted",
        )

        selected = pool.acquire_account()
        self.assertEqual(selected["id"], account_id)

        health = self.store.get_health(account_id)
        assert health is not None
        self.assertEqual(health["runtime_status"], "active")

    def test_usage_limited_cooldown_until_next_midnight(self) -> None:
        account_id = self._create_active_account()
        pool = AccountPool(self.store, cooldown_seconds=60, failure_threshold=3)

        pool.mark_usage_limited(account_id)

        health = self.store.get_health(account_id)
        assert health is not None
        cooldown = datetime.fromisoformat(health["cooldown_until"])
        # Cooldown should be at midnight (hour=0, minute=0)
        self.assertEqual(cooldown.hour, 0)
        self.assertEqual(cooldown.minute, 0)
        self.assertEqual(cooldown.second, 0)


if __name__ == "__main__":
    unittest.main()
