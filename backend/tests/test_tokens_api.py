"""Tests for token management API endpoints."""

from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app import app
from src.middleware.auth import AdminContext, require_admin_token


class TokensApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._old_cwd = os.getcwd()
        self._old_env = {
            "REGISTER_BOT_STORAGE__TOKENS_DB_PATH": os.environ.get("REGISTER_BOT_STORAGE__TOKENS_DB_PATH"),
        }
        os.chdir(self._tmp_dir.name)
        os.makedirs("config", exist_ok=True)
        os.environ["REGISTER_BOT_STORAGE__TOKENS_DB_PATH"] = f"{self._tmp_dir.name}/tokens.db"
        app.dependency_overrides[require_admin_token] = lambda: AdminContext(username="test-admin")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        os.chdir(self._old_cwd)
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        app.dependency_overrides.pop(require_admin_token, None)
        self._tmp_dir.cleanup()

    def test_tokens_crud(self) -> None:
        create_response = self.client.post("/api/tokens", json={"name": "integration"})
        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertIn("key", created)
        self.assertTrue(created["key"].startswith("sk-"))
        token_id = created["id"]

        list_response = self.client.get("/api/tokens")
        self.assertEqual(list_response.status_code, 200)
        tokens = list_response.json()
        self.assertEqual(len(tokens), 1)
        self.assertTrue(tokens[0]["key"].endswith("****"))

        revoke_response = self.client.delete(f"/api/tokens/{token_id}")
        self.assertEqual(revoke_response.status_code, 200)
        self.assertEqual(revoke_response.json()["status"], "revoked")

        delete_response = self.client.delete(f"/api/tokens/{token_id}/permanent")
        self.assertEqual(delete_response.status_code, 204)


if __name__ == "__main__":
    unittest.main()
