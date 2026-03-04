"""Tests for background account health checker."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

from src.services.health_checker import HealthChecker
from src.storage.account_store import AccountStore


class HealthCheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.store = AccountStore(f"{self._tmp_dir.name}/accounts.db", "test-key-1234567890")

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def _create_active_account(self) -> int:
        return self.store.save_account(
            {
                "email": "probe@example.com",
                "password": "secret",
                "status": "active",
                "openai_token": "upstream-token",
                "plan": "free",
            }
        )

    def test_recovery_from_cooling(self) -> None:
        account_id = self._create_active_account()
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self.store.update_health(
            account_id,
            runtime_status="cooling",
            consecutive_failures=2,
            cooldown_until=past,
        )
        chat_client = Mock()
        chat_client.list_models = AsyncMock(return_value={"object": "list", "data": []})
        checker = HealthChecker(self.store, chat_client, cooldown_seconds=60, failure_threshold=3)

        asyncio.run(checker.check_once())

        health = self.store.get_health(account_id)
        self.assertIsNotNone(health)
        assert health is not None
        self.assertEqual(health["runtime_status"], "active")
        self.assertEqual(health["consecutive_failures"], 0)

    def test_probe_success_clears_failures(self) -> None:
        account_id = self._create_active_account()
        self.store.update_health(
            account_id,
            runtime_status="active",
            consecutive_failures=2,
            total_failures=2,
            cooldown_until=None,
        )
        chat_client = Mock()
        chat_client.list_models = AsyncMock(return_value={"object": "list", "data": []})
        checker = HealthChecker(self.store, chat_client, cooldown_seconds=60, failure_threshold=3)

        asyncio.run(checker.check_once())

        health = self.store.get_health(account_id)
        self.assertIsNotNone(health)
        assert health is not None
        self.assertEqual(health["runtime_status"], "active")
        self.assertEqual(health["consecutive_failures"], 0)
        self.assertIsNotNone(health["last_success_at"])

    def test_probe_failure_triggers_cooling(self) -> None:
        account_id = self._create_active_account()
        chat_client = Mock()
        chat_client.list_models = AsyncMock(side_effect=RuntimeError("boom"))
        checker = HealthChecker(self.store, chat_client, cooldown_seconds=60, failure_threshold=3)

        asyncio.run(checker.check_once())

        health = self.store.get_health(account_id)
        self.assertIsNotNone(health)
        assert health is not None
        self.assertEqual(health["runtime_status"], "cooling")
        self.assertEqual(health["consecutive_failures"], 1)
        self.assertIsNotNone(health["cooldown_until"])
        self.assertEqual(health["last_failure_reason"], "boom")


if __name__ == "__main__":
    unittest.main()
