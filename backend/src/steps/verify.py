"""Verification steps placeholders."""

from __future__ import annotations

import structlog

from src.integrations.openai_api import OpenAIRegistrationClient
from src.pipeline.base import Step, StepResult
from src.pipeline.context import PipelineContext


class VerifyEmailStep(Step):
    """Verify account email with OpenAI token/code."""

    name = "verify_email"
    description = "Verify account email address"

    def __init__(self) -> None:
        self._logger = structlog.get_logger(self.__class__.__name__)

    async def execute(self, context: PipelineContext) -> StepResult:
        settings = context.get("settings")
        if settings is None:
            return StepResult(success=False, error="Settings missing in context metadata")
        if not context.email:
            return StepResult(success=False, error="email missing in context")
        if not context.verification_code:
            return StepResult(success=False, error="verification_code missing in context")

        csrf_token = str(context.metadata.get("csrf_token", ""))
        if not csrf_token:
            return StepResult(success=False, error="csrf_token missing in metadata")

        client = OpenAIRegistrationClient(
            auth_url=settings.openai.auth_url,
            oauth_client_id=settings.openai.oauth_client_id,
            timeout=settings.openai.timeout_seconds,
            proxy=settings.network.openai_proxy or settings.network.http_proxy,
        )
        try:
            result = await client.verify_email(
                email=context.email,
                code=context.verification_code,
                csrf_token=csrf_token,
            )
        except Exception as exc:  # noqa: BLE001
            return StepResult(success=False, error=f"verify_email_failed: {exc}")

        if not result.get("verified", False):
            return StepResult(success=False, error="verify_email_failed: verification not confirmed")
        authorization_code = str(result.get("authorization_code", ""))
        if not authorization_code:
            return StepResult(success=False, error="verify_email_failed: missing authorization_code")
        self._logger.info("email_verified", email=context.email)
        return StepResult(success=True, data={"authorization_code": authorization_code})


class VerifyPhoneStep(Step):
    """Verify phone number challenge."""

    name = "verify_phone"
    description = "Verify phone number"

    async def execute(self, context: PipelineContext) -> StepResult:
        settings = context.get("settings")
        if settings is None:
            return StepResult(success=False, error="Settings missing in context metadata")

        if settings.registration.skip_phone_verification:
            return StepResult(success=True, skip_reason="skip_phone_verification enabled")
        return StepResult(success=False, error="Phone verification requires manual completion")
