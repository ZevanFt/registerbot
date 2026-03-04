"""Tests for OpenAI-compatible proxy endpoints."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

import api.openai_proxy as openai_proxy
from app import app
from src.middleware.auth import AdminContext, require_admin_token


class OpenAIProxyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._old_env = {
            "REGISTER_BOT_STORAGE__DB_PATH": os.environ.get("REGISTER_BOT_STORAGE__DB_PATH"),
            "REGISTER_BOT_STORAGE__TOKENS_DB_PATH": os.environ.get("REGISTER_BOT_STORAGE__TOKENS_DB_PATH"),
            "REGISTER_BOT_STORAGE__STATS_DB_PATH": os.environ.get("REGISTER_BOT_STORAGE__STATS_DB_PATH"),
            "REGISTER_BOT_STORAGE__ENCRYPTION_KEY": os.environ.get("REGISTER_BOT_STORAGE__ENCRYPTION_KEY"),
        }
        os.environ["REGISTER_BOT_STORAGE__DB_PATH"] = f"{self._tmp_dir.name}/accounts.db"
        os.environ["REGISTER_BOT_STORAGE__TOKENS_DB_PATH"] = f"{self._tmp_dir.name}/tokens.db"
        os.environ["REGISTER_BOT_STORAGE__STATS_DB_PATH"] = f"{self._tmp_dir.name}/stats.db"
        os.environ["REGISTER_BOT_STORAGE__ENCRYPTION_KEY"] = "test-key-1234567890"
        openai_proxy._account_pool = None
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

    def _create_token(self) -> str:
        response = self.client.post("/api/tokens", json={"name": "proxy-test"})
        self.assertEqual(response.status_code, 201)
        return response.json()["key"]

    def _create_account(self) -> None:
        response = self.client.post(
            "/api/accounts",
            json={
                "email": "proxy@example.com",
                "password": "secret",
                "status": "active",
                "openai_token": "upstream-account-token",
                "plan": "free",
            },
        )
        self.assertEqual(response.status_code, 201)

    def test_no_auth_returns_401(self) -> None:
        response = self.client.get("/v1/models")

        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "unauthorized")

    def test_invalid_token_returns_401(self) -> None:
        response = self.client.get("/v1/models", headers={"Authorization": "Bearer sk-invalid"})

        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["error"]["code"], "invalid_api_key")

    def test_list_models(self) -> None:
        token = self._create_token()
        self._create_account()

        response = self.client.get("/v1/models", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["object"], "list")
        self.assertGreater(len(payload["data"]), 0)
        # In chat2api mode (localhost base_url), returns static model list
        model_ids = [m["id"] for m in payload["data"]]
        self.assertIn("gpt-4o-mini", model_ids)

    def test_chat_completions_non_stream(self) -> None:
        token = self._create_token()
        self._create_account()

        fake_client = Mock()
        fake_client.chat_completions = AsyncMock(
            return_value=(
                200,
                {
                    "id": "chatcmpl-1",
                    "object": "chat.completion",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": "hello"}}],
                    "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
                },
            )
        )

        with patch("api.openai_proxy._build_chat_client", return_value=fake_client):
            response = self.client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "model": "gpt-4.1-mini",
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["choices"][0]["message"]["content"], "hello")

    def test_chat_completions_stream_sse(self) -> None:
        token = self._create_token()
        self._create_account()

        class FakeStreamClient:
            async def chat_completions_stream(self, _api_key: str, _payload: dict):
                yield b'data: {"id":"chatcmpl-1","object":"chat.completion.chunk"}\n\n'
                yield b"data: [DONE]\n\n"

        with patch("api.openai_proxy._build_chat_client", return_value=FakeStreamClient()):
            response = self.client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "model": "gpt-4.1-mini",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        self.assertIn("data: [DONE]", response.text)


if __name__ == "__main__":
    unittest.main()
