"""Tests for runtime logs API endpoints."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app import app
from src.middleware.auth import AdminContext, require_admin_token
from src.utils.log_collector import LogCollector


class LogsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[require_admin_token] = lambda: AdminContext(username="test-admin")
        self.client = TestClient(app)
        self.collector = LogCollector()
        self.collector.clear()
        self.collector.add("INFO", "startup complete", source="system")
        self.collector.add("ERROR", "token create failed", source="tokens")

    def tearDown(self) -> None:
        self.collector.clear()
        app.dependency_overrides.pop(require_admin_token, None)

    def test_get_logs_returns_items(self) -> None:
        response = self.client.get("/api/logs")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(len(payload["items"]), 2)

    def test_get_logs_filters_by_level(self) -> None:
        response = self.client.get("/api/logs", params={"level": "ERROR"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["level"], "ERROR")

    def test_delete_logs_clears_collector(self) -> None:
        response = self.client.delete("/api/logs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "cleared")

        check_response = self.client.get("/api/logs")
        self.assertEqual(check_response.status_code, 200)
        self.assertEqual(check_response.json()["total"], 0)


if __name__ == "__main__":
    unittest.main()
