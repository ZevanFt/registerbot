"""Tests for dashboard and accounts FastAPI endpoints."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app import app
from src.middleware.auth import AdminContext, require_admin_token
from src.storage.stats_store import StatsStore


class DashboardApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._old_env = {
            "REGISTER_BOT_STORAGE__DB_PATH": os.environ.get("REGISTER_BOT_STORAGE__DB_PATH"),
            "REGISTER_BOT_STORAGE__ENCRYPTION_KEY": os.environ.get("REGISTER_BOT_STORAGE__ENCRYPTION_KEY"),
            "REGISTER_BOT_STORAGE__STATS_DB_PATH": os.environ.get("REGISTER_BOT_STORAGE__STATS_DB_PATH"),
        }
        os.environ["REGISTER_BOT_STORAGE__DB_PATH"] = f"{self._tmp_dir.name}/accounts.db"
        os.environ["REGISTER_BOT_STORAGE__ENCRYPTION_KEY"] = "test-key-1234567890"
        os.environ["REGISTER_BOT_STORAGE__STATS_DB_PATH"] = f"{self._tmp_dir.name}/stats.db"
        app.dependency_overrides[require_admin_token] = lambda: AdminContext(username="test-admin")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        app.dependency_overrides.pop(require_admin_token, None)
        self._tmp_dir.cleanup()

    def test_dashboard_stats_shape(self) -> None:
        response = self.client.get("/api/dashboard/stats")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("accounts", payload)
        self.assertIn("usage", payload)
        self.assertIn("models", payload)
        self.assertIn("service", payload)
        self.assertEqual(payload["accounts"]["total"], 0)
        self.assertEqual(payload["usage"]["today_requests"], 0)
        self.assertIn("success_rate", payload["usage"])
        self.assertIn("current_tpm", payload["usage"])
        self.assertEqual(payload["usage"]["success_rate"], 0.0)
        self.assertEqual(payload["usage"]["current_tpm"], 0)
        self.assertEqual(payload["service"]["schedule_mode"], "round-robin")

    def test_dashboard_stats_uses_real_usage_data(self) -> None:
        stats_store = StatsStore(os.environ["REGISTER_BOT_STORAGE__STATS_DB_PATH"])
        now = datetime.now(timezone.utc)
        recent_iso = (now - timedelta(seconds=20)).isoformat()
        today_iso = (now - timedelta(hours=2)).isoformat()
        yesterday_iso = (now - timedelta(days=1)).isoformat()

        stats_store.append_usage_log(
            timestamp=today_iso,
            account_id=1,
            model="gpt-4o-mini",
            request_tokens=10,
            response_tokens=20,
            status_code=200,
        )
        stats_store.append_usage_log(
            timestamp=today_iso,
            account_id=1,
            model="gpt-4o-mini",
            request_tokens=5,
            response_tokens=15,
            status_code=500,
        )
        stats_store.append_usage_log(
            timestamp=recent_iso,
            account_id=2,
            model="gpt-4o",
            request_tokens=7,
            response_tokens=3,
            status_code=200,
        )
        stats_store.append_usage_log(
            timestamp=yesterday_iso,
            account_id=3,
            model="gpt-4o",
            request_tokens=100,
            response_tokens=100,
            status_code=200,
        )

        response = self.client.get("/api/dashboard/stats")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["usage"]["today_requests"], 3)
        self.assertEqual(payload["usage"]["today_tokens"], 60)
        self.assertEqual(payload["usage"]["current_rpm"], 1)
        self.assertEqual(payload["usage"]["current_tpm"], 10)
        self.assertAlmostEqual(payload["usage"]["success_rate"], 66.67, places=2)

    def test_accounts_crud(self) -> None:
        create_response = self.client.post(
            "/api/accounts",
            json={"email": "a@example.com", "password": "secret", "plan": "free", "status": "active"},
        )
        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["email"], "a@example.com")
        self.assertEqual(created["status"], "active")
        self.assertEqual(created["runtime_status"], "active")
        self.assertEqual(created["token_status"], "unknown")
        self.assertEqual(created["consecutive_failures"], 0)

        list_response = self.client.get("/api/accounts")
        self.assertEqual(list_response.status_code, 200)
        accounts = list_response.json()
        self.assertEqual(len(accounts), 1)
        self.assertIn("runtime_status", accounts[0])
        self.assertIn("token_status", accounts[0])
        self.assertIn("consecutive_failures", accounts[0])
        self.assertIn("last_failure_reason", accounts[0])
        account_id = accounts[0]["id"]

        patch_response = self.client.patch(f"/api/accounts/{account_id}", json={"status": "banned"})
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()["status"], "banned")

        delete_response = self.client.delete(f"/api/accounts/{account_id}")
        self.assertEqual(delete_response.status_code, 204)

        list_after_delete = self.client.get("/api/accounts")
        self.assertEqual(list_after_delete.status_code, 200)
        self.assertEqual(list_after_delete.json(), [])

    def test_accounts_reveal_export_import(self) -> None:
        first = self.client.post(
            "/api/accounts",
            json={"email": "first@example.com", "password": "secret-1", "plan": "free", "status": "active"},
        )
        second = self.client.post(
            "/api/accounts",
            json={"email": "second@example.com", "password": "secret-2", "plan": "plus", "status": "active"},
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        first_id = int(first.json()["id"])

        reveal = self.client.get(f"/api/accounts/{first_id}/password/reveal")
        self.assertEqual(reveal.status_code, 200)
        self.assertEqual(reveal.json()["password"], "secret-1")

        exported = self.client.get(f"/api/accounts/export?ids={first_id}")
        self.assertEqual(exported.status_code, 200)
        payload = exported.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["accounts"][0]["email"], "first@example.com")
        self.assertIn("password", payload["accounts"][0])

        import_payload = {
            "conflict_strategy": "overwrite",
            "accounts": [
                {
                    "email": "first@example.com",
                    "password": "new-secret",
                    "plan": "plus",
                    "status": "active",
                    "token_status": "valid",
                },
                {
                    "email": "third@example.com",
                    "password": "secret-3",
                    "plan": "free",
                    "status": "active",
                },
            ],
        }
        imported = self.client.post("/api/accounts/import", json=import_payload)
        self.assertEqual(imported.status_code, 200)
        self.assertEqual(imported.json()["updated"], 1)
        self.assertEqual(imported.json()["imported"], 1)

        reveal_after = self.client.get(f"/api/accounts/{first_id}/password/reveal")
        self.assertEqual(reveal_after.status_code, 200)
        self.assertEqual(reveal_after.json()["password"], "new-secret")


if __name__ == "__main__":
    unittest.main()
