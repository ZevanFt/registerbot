"""Tests for registration pipeline and API."""

from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import api.pipeline_api as pipeline_api
from app import app
from src.config.settings import load_settings
from src.middleware.auth import AdminContext, require_admin_token
from src.pipeline.context import PipelineContext
from src.services.registration_service import RegistrationService
from src.steps.verify import VerifyPhoneStep
from src.storage.account_store import AccountStore


class RegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._old_env = {
            "REGISTER_BOT_STORAGE__DB_PATH": os.environ.get("REGISTER_BOT_STORAGE__DB_PATH"),
            "REGISTER_BOT_STORAGE__ENCRYPTION_KEY": os.environ.get("REGISTER_BOT_STORAGE__ENCRYPTION_KEY"),
            "REGISTER_BOT_OPENAI__DEFAULT_PASSWORD": os.environ.get("REGISTER_BOT_OPENAI__DEFAULT_PASSWORD"),
            "REGISTER_BOT_OPENAI__OAUTH_CLIENT_ID": os.environ.get("REGISTER_BOT_OPENAI__OAUTH_CLIENT_ID"),
        }
        os.environ["REGISTER_BOT_STORAGE__DB_PATH"] = f"{self._tmp_dir.name}/accounts.db"
        os.environ["REGISTER_BOT_STORAGE__ENCRYPTION_KEY"] = "test-key-1234567890"
        os.environ["REGISTER_BOT_OPENAI__DEFAULT_PASSWORD"] = "default-pass-123"
        os.environ["REGISTER_BOT_OPENAI__OAUTH_CLIENT_ID"] = "test-client-id"
        pipeline_api._registration_service = None
        app.dependency_overrides[require_admin_token] = lambda: AdminContext(username="test-admin")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        app.dependency_overrides.pop(require_admin_token, None)
        pipeline_api._registration_service = None
        self._tmp_dir.cleanup()

    @contextmanager
    def _patch_registration_dependencies(self):
        """Mock browser-based steps and OpenAI API client for testing."""
        from src.pipeline.base import StepResult

        async def mock_browser_signup(context):
            new_metadata = {
                **context.metadata,
                "code_verifier": "verifier-1",
                "code_challenge": "challenge-1",
                "oauth_state": "state-1",
                "browser_session_id": "mock-session-1",
                "_browser_manager": None,
            }
            return StepResult(success=True, data={"metadata": new_metadata})

        async def mock_browser_verify(context):
            return StepResult(success=True, data={"authorization_code": "auth-code-1"})

        with (
            patch.multiple(
                "src.integrations.openai_api.OpenAIRegistrationClient",
                exchange_code_for_tokens=AsyncMock(
                    return_value={"access_token": "access-1", "refresh_token": "refresh-1", "expires_in": 3600}
                ),
                set_profile=AsyncMock(return_value={"name": "API User"}),
                create_session=AsyncMock(return_value={"session_id": "sess-1"}),
            ),
            patch(
                "src.steps.browser_signup.BrowserSignupStep.execute",
                side_effect=mock_browser_signup,
            ),
            patch(
                "src.steps.browser_verify.BrowserVerifyEmailStep.execute",
                side_effect=mock_browser_verify,
            ),
        ):
            yield

    def _patch_mail_dependencies(self):
        return patch.multiple(
            "src.integrations.talentmail.TalentMailClient",
            create_temp_email=AsyncMock(return_value={"id": "mailbox-1", "email": "bot@example.com"}),
            wait_for_code=AsyncMock(return_value="123456"),
        )

    def test_registration_pipeline_success(self) -> None:
        settings = load_settings()
        store = AccountStore(settings.storage.db_path, settings.storage.encryption_key)
        service = RegistrationService(settings=settings, account_store=store)

        with self._patch_registration_dependencies(), self._patch_mail_dependencies():
            result = self._run(service.register_account(email="seed@example.com", password="pwd-123"))

        self.assertTrue(result["success"])
        self.assertEqual(result["steps_completed"], 8)
        self.assertEqual(result["steps_failed"], 0)

    def test_skip_phone_verification(self) -> None:
        settings = load_settings()
        ctx = PipelineContext(metadata={"settings": settings})
        result = self._run(VerifyPhoneStep().execute(ctx))

        self.assertTrue(result.success)
        self.assertEqual(result.skip_reason, "skip_phone_verification enabled")

    def test_registration_saves_account(self) -> None:
        settings = load_settings()
        store = AccountStore(settings.storage.db_path, settings.storage.encryption_key)
        service = RegistrationService(settings=settings, account_store=store)

        with self._patch_registration_dependencies(), self._patch_mail_dependencies():
            result = self._run(service.register_account(email="seed@example.com", password="pwd-123"))

        self.assertTrue(result["success"])
        accounts = store.list_accounts()
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]["email"], "bot@example.com")
        self.assertEqual(accounts[0]["openai_token"], "access-1")
        self.assertEqual(accounts[0]["refresh_token"], "refresh-1")
        self.assertEqual(accounts[0]["token_status"], "valid")
        self.assertEqual(accounts[0]["status"], "active")
        self.assertIsNotNone(accounts[0]["token_expires_at"])

    def test_registration_api_endpoint(self) -> None:
        with self._patch_registration_dependencies(), self._patch_mail_dependencies():
            response = self.client.post(
                "/api/pipeline/register",
                json={"email": "api@example.com", "password": "pwd-123"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["steps_failed"], 0)

    def test_registration_mode_http_uses_http_steps(self) -> None:
        settings = load_settings()
        settings.registration.mode = "http"
        service = RegistrationService(
            settings=settings,
            account_store=AccountStore(settings.storage.db_path, settings.storage.encryption_key),
        )

        steps = service._build_steps("http")
        step_names = [step.name for step in steps]

        self.assertIn("submit_registration", step_names)
        self.assertIn("verify_email", step_names)
        self.assertNotIn("browser_signup", step_names)
        self.assertNotIn("browser_verify_email", step_names)

    def _run(self, awaitable):
        import asyncio

        return asyncio.run(awaitable)


if __name__ == "__main__":
    unittest.main()
