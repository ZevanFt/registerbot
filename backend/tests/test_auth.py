"""Tests for admin auth API endpoints."""

from __future__ import annotations

import os
import unittest

from fastapi.testclient import TestClient

from app import app


class AuthApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_env = {
            "REGISTER_BOT_ADMIN__USERNAME": os.environ.get("REGISTER_BOT_ADMIN__USERNAME"),
            "REGISTER_BOT_ADMIN__PASSWORD": os.environ.get("REGISTER_BOT_ADMIN__PASSWORD"),
            "REGISTER_BOT_ADMIN__JWT_SECRET": os.environ.get("REGISTER_BOT_ADMIN__JWT_SECRET"),
            "REGISTER_BOT_ADMIN__JWT_EXPIRE_HOURS": os.environ.get("REGISTER_BOT_ADMIN__JWT_EXPIRE_HOURS"),
        }
        os.environ["REGISTER_BOT_ADMIN__USERNAME"] = "admin"
        os.environ["REGISTER_BOT_ADMIN__PASSWORD"] = "admin123"
        os.environ["REGISTER_BOT_ADMIN__JWT_SECRET"] = "test-secret"
        os.environ["REGISTER_BOT_ADMIN__JWT_EXPIRE_HOURS"] = "24"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_login_success(self) -> None:
        response = self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["username"], "admin")
        self.assertIsInstance(payload["token"], str)
        self.assertTrue(payload["token"])

    def test_login_wrong_password(self) -> None:
        response = self.client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})

        self.assertEqual(response.status_code, 401)

    def test_me_with_valid_token(self) -> None:
        login_response = self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(login_response.status_code, 200)
        token = login_response.json()["token"]

        response = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "admin")

    def test_me_without_token(self) -> None:
        response = self.client.get("/api/auth/me")

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
