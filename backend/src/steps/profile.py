"""Profile setup step placeholder."""

from __future__ import annotations

import structlog

from src.integrations.openai_api import OpenAIRegistrationClient
from src.pipeline.base import Step, StepResult
from src.pipeline.context import PipelineContext


class SetProfileStep(Step):
    """Set OpenAI profile fields."""

    name = "set_profile"
    description = "Set initial profile"

    def __init__(self) -> None:
        self._logger = structlog.get_logger(self.__class__.__name__)

    async def execute(self, context: PipelineContext) -> StepResult:
        settings = context.get("settings")
        if settings is None:
            return StepResult(success=False, error="Settings missing in context metadata")
        if not context.access_token:
            return StepResult(success=False, error="access_token missing in context")

        # If token came from browser session, profile was already set during onboarding
        if context.get("registered"):
            self._logger.info("profile_skip", reason="profile set during browser onboarding")
            return StepResult(
                success=True,
                skip_reason="profile already set during browser onboarding",
                data={},
            )

        client = OpenAIRegistrationClient(
            auth_url=settings.openai.auth_url,
            oauth_client_id=settings.openai.oauth_client_id,
            timeout=settings.openai.timeout_seconds,
            proxy=settings.network.openai_proxy or settings.network.http_proxy,
        )
        try:
            profile = await client.set_profile(
                access_token=context.access_token,
                name=settings.registration.profile_name,
            )
            session = await client.create_session(access_token=context.access_token)
        except Exception as exc:  # noqa: BLE001
            return StepResult(success=False, error=f"set_profile_failed: {exc}")

        account_info = {
            **context.account_info,
            "profile": profile,
            "session": session,
        }
        self._logger.info("profile_set", email=context.email)
        return StepResult(success=True, data={"account_info": account_info})
