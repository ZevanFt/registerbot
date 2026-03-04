"""Tests for account health persistence and account pool behavior."""

from __future__ import annotations

import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
