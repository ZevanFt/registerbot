"""Registration pipeline service."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from src.pipeline import Pipeline, PipelineContext, PipelineRunner
from src.steps import (
    BrowserSignupStep,
    BrowserVerifyEmailStep,
    CreateTempEmailStep,
    SetPasswordStep,
    SetProfileStep,
    SubmitRegistrationStep,
    UpgradePlusStep,
    VerifyEmailStep,
    VerifyPhoneStep,
    WaitForVerificationCodeStep,
)


class RegistrationService:
    """Compose and execute the registration automation pipeline."""

    def __init__(self, settings: Any, account_store: Any) -> None:
        self.settings = settings
        self.account_store = account_store
        self._runner = PipelineRunner(max_retries=1, retry_delay=0)
        self._status: dict[str, Any] = {"running": False, "last_result": None}

    async def register_account(
        self,
        email: str,
        password: str,
        event_callback: Callable[[dict[str, object]], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        registration_mode = str(getattr(self.settings.registration, "mode", "browser")).lower()
        pipeline = Pipeline(
            name="openai_registration",
            description="OpenAI registration automation pipeline",
            steps=self._build_steps(registration_mode),
        )
        initial_context = PipelineContext(
            email=email,
            password=password,
            metadata={"settings": self.settings},
        )
        self._status["running"] = True
        try:
            result = await self._runner.run(pipeline, initial_context, event_callback=event_callback)
            final_context = self._build_final_context(initial_context, result.results)
            response = {
                "success": result.success,
                "steps_completed": result.steps_completed,
                "steps_failed": result.steps_failed,
                "total_duration": result.total_duration,
                "errors": {name: item.error for name, item in result.results.items() if item.error},
                "email": final_context.email,
            }
            if not result.success:
                self._status["last_result"] = response
                return response

            expires_in = int(final_context.get("expires_in", 0))
            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=expires_in if expires_in > 0 else 86400)
            ).isoformat()
            self.account_store.save_account(
                {
                    "email": final_context.email or email,
                    "password": final_context.password or password,
                    "openai_token": final_context.access_token,
                    "refresh_token": final_context.get("refresh_token"),
                    "token_expires_at": expires_at,
                    "token_status": "valid",
                    # Account is ready for serving traffic once token is available.
                    "status": "active",
                    "plan": "free",
                }
            )
            self._status["last_result"] = response
            return response
        finally:
            self._status["running"] = False

    def get_status(self) -> dict[str, Any]:
        return dict(self._status)

    def _build_final_context(
        self, initial_context: PipelineContext, results: dict[str, Any]
    ) -> PipelineContext:
        context = initial_context
        for step_result in results.values():
            if not step_result.success:
                break
            for key, value in step_result.data.items():
                context = context.set(key, value)
        return context

    def _build_steps(self, mode: str) -> list[Any]:
        if mode == "http":
            return [
                CreateTempEmailStep(),
                SubmitRegistrationStep(),
                WaitForVerificationCodeStep(),
                VerifyEmailStep(),
                VerifyPhoneStep(),
                SetPasswordStep(),
                SetProfileStep(),
                UpgradePlusStep(),
            ]
        return [
            CreateTempEmailStep(),
            BrowserSignupStep(),
            WaitForVerificationCodeStep(),
            BrowserVerifyEmailStep(),
            VerifyPhoneStep(),
            SetPasswordStep(),
            SetProfileStep(),
            UpgradePlusStep(),
        ]
