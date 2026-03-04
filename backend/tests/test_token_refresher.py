"""Tests for token refresh background service."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import httpx

from src.services.health_checker import HealthChecker
from src.services.token_refresher import TokenRefresher, TokenRefresherSettings
from src.storage.account_store import AccountStore


class TokenRefresherTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.store = AccountStore(f"{self._tmp_dir.name}/accounts.db", "test-key-1234567890")
        self.settings = TokenRefresherSettings(
            oauth_client_id="client-id",
            oauth_client_secret="client-secret",
            token_url="https://auth0.openai.com/oauth/token",
            refresh_interval=1,
            skew_seconds=300,
            timeout=3.0,
            max_retries=1,
            backoff_seconds=0,
        )

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_refresh_success(self) -> None:
        account_id = self.store.save_account(
            {
                "email": "refresh-success@example.com",
                "password": "secret",
                "status": "active",
                "openai_token": "old-token",
                "refresh_token": "refresh-old",
                "token_expires_at": (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(),
                "token_status": "valid",
            }
        )
        client = Mock()
        client.refresh_access_token = AsyncMock(
            return_value={
                "access_token": "new-token",
                "expires_in": 3600,
                "refresh_token": "refresh-new",
            }
        )
        refresher = TokenRefresher(self.store, client, self.settings)

        asyncio.run(refresher.refresh_once())

        updated = self.store.get_account(account_id)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["openai_token"], "new-token")
        self.assertEqual(updated["refresh_token"], "refresh-new")
        self.assertEqual(updated["token_status"], "valid")
        self.assertEqual(updated["token_refresh_attempts"], 0)
        self.assertIsNone(updated["token_refresh_error"])
        self.assertIsNotNone(updated["token_last_refreshed_at"])
        self.assertGreater(datetime.fromisoformat(str(updated["token_expires_at"])), datetime.now(timezone.utc))

    def test_refresh_invalid_grant(self) -> None:
        account_id = self.store.save_account(
            {
                "email": "refresh-invalid@example.com",
                "password": "secret",
                "status": "active",
                "openai_token": "old-token",
                "refresh_token": "refresh-old",
                "token_expires_at": (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(),
                "token_status": "expired",
            }
        )
        client = Mock()
        client.refresh_access_token = AsyncMock(side_effect=RuntimeError("invalid_grant: token revoked"))
        refresher = TokenRefresher(self.store, client, self.settings)

        asyncio.run(refresher.refresh_once())

        updated = self.store.get_account(account_id)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["token_status"], "invalid_grant")
        self.assertEqual(updated["token_refresh_attempts"], 1)
        self.assertIn("invalid_grant", str(updated["token_refresh_error"]))

    def test_skip_non_expiring(self) -> None:
        self.store.save_account(
            {
                "email": "refresh-skip@example.com",
                "password": "secret",
                "status": "active",
                "openai_token": "old-token",
                "refresh_token": "refresh-old",
                "token_expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "token_status": "valid",
            }
        )
        client = Mock()
        client.refresh_access_token = AsyncMock(
            return_value={
                "access_token": "new-token",
                "expires_in": 3600,
            }
        )
        refresher = TokenRefresher(self.store, client, self.settings)

        asyncio.run(refresher.refresh_once())

        client.refresh_access_token.assert_not_awaited()

    def test_health_checker_401_not_counted_as_failure(self) -> None:
        account_id = self.store.save_account(
            {
                "email": "health-401@example.com",
                "password": "secret",
                "status": "active",
                "openai_token": "upstream-token",
                "token_status": "valid",
            }
        )
        req = httpx.Request("GET", "https://api.openai.com/v1/models")
        resp = httpx.Response(401, request=req, json={"error": {"message": "unauthorized"}})
        chat_client = Mock()
        chat_client.list_models = AsyncMock(side_effect=httpx.HTTPStatusError("401", request=req, response=resp))
        checker = HealthChecker(self.store, chat_client, cooldown_seconds=60, failure_threshold=3)

        asyncio.run(checker.check_once())

        health = self.store.get_health(account_id)
        account = self.store.get_account(account_id)
        self.assertIsNotNone(health)
        self.assertIsNotNone(account)
        assert health is not None
        assert account is not None
        self.assertEqual(health["consecutive_failures"], 0)
        self.assertEqual(health["total_failures"], 0)
        self.assertEqual(account["token_status"], "expired")


if __name__ == "__main__":
    unittest.main()
