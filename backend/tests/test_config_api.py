"""Tests for configuration API endpoints."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app import app
from src.middleware.auth import AdminContext, require_admin_token


class ConfigApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._old_cwd = os.getcwd()
        os.chdir(self._tmp_dir.name)
        config_dir = Path("config")
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "settings.yaml").write_text(
            yaml.dump(
                {
                    "talentmail": {
                        "base_url": "http://localhost/api",
                        "email": "admin@example.com",
                        "password": "secret",
                    },
                    "openai": {"register_url": "https://chat.openai.com"},
                    "storage": {
                        "db_path": "data/accounts.db",
                        "tokens_db_path": "data/tokens.db",
                        "stats_db_path": "data/stats.db",
                        "encryption_key": "enc-key",
                    },
                    "logging": {"level": "INFO", "format": "json"},
                },
                allow_unicode=True,
                default_flow_style=False,
            ),
            encoding="utf-8",
        )
        app.dependency_overrides[require_admin_token] = lambda: AdminContext(username="test-admin")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        os.chdir(self._old_cwd)
        app.dependency_overrides.pop(require_admin_token, None)
        self._tmp_dir.cleanup()

    def test_get_config_masks_secret_fields(self) -> None:
        response = self.client.get("/api/config")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["talentmail"]["password"], "***")
        self.assertEqual(payload["storage"]["encryption_key"], "***")

    def test_put_config_updates_and_persists(self) -> None:
        update_response = self.client.put(
            "/api/config",
            json={
                "talentmail": {"email": "updated@example.com", "password": "***"},
                "logging": {"level": "DEBUG"},
            },
        )
        self.assertEqual(update_response.status_code, 200)

        get_response = self.client.get("/api/config")
        self.assertEqual(get_response.status_code, 200)
        payload = get_response.json()
        self.assertEqual(payload["talentmail"]["email"], "updated@example.com")
        self.assertEqual(payload["logging"]["level"], "DEBUG")
        self.assertEqual(payload["talentmail"]["password"], "***")

        file_payload = yaml.safe_load(Path("config/settings.yaml").read_text(encoding="utf-8"))
        self.assertEqual(file_payload["talentmail"]["email"], "updated@example.com")
        self.assertEqual(file_payload["talentmail"]["password"], "secret")


if __name__ == "__main__":
    unittest.main()
