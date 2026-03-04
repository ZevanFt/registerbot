"""Registration submission step."""

from __future__ import annotations

import structlog

from src.integrations.openai_api import OpenAIRegistrationClient
from src.pipeline.base import Step, StepResult
from src.pipeline.context import PipelineContext


class SubmitRegistrationStep(Step):
    """Submit OpenAI registration request.

    Expected flow:
    1. Validate required context fields (email and password).
    2. Build HTTP session and anti-bot headers/cookies.
    3. Submit registration payload to OpenAI register endpoint.
    4. Parse response and persist request/session metadata for follow-up steps.
    5. Return structured result with identifiers used by email verification.
    """

    name = "submit_registration"
    description = "Submit registration request to OpenAI"

    def __init__(self) -> None:
        self._logger = structlog.get_logger(self.__class__.__name__)

    async def execute(self, context: PipelineContext) -> StepResult:
        settings = context.get("settings")
        if settings is None:
            return StepResult(success=False, error="Settings missing in context metadata")
        if not context.email:
            return StepResult(success=False, error="email missing in context")
        if not context.password:
            return StepResult(success=False, error="password missing in context")

        client = OpenAIRegistrationClient(
            auth_url=settings.openai.auth_url,
            oauth_client_id=settings.openai.oauth_client_id,
            timeout=settings.openai.timeout_seconds,
            proxy=settings.network.openai_proxy or settings.network.http_proxy,
        )
        try:
            auth_data = await client.init_auth_session(settings.openai.auth_url)
            submit_result = await client.submit_registration(
                email=context.email,
                password=context.password,
                csrf_token=str(auth_data["csrf_token"]),
                turnstile_token="",
            )
        except Exception as exc:  # noqa: BLE001
            return StepResult(success=False, error=f"submit_registration_failed: {exc}")

        if not submit_result.get("success", False):
            return StepResult(success=False, error="submit_registration_failed: upstream rejected registration")

        new_metadata = {
            **context.metadata,
            "csrf_token": str(auth_data["csrf_token"]),
            "code_verifier": str(auth_data["code_verifier"]),
            "oauth_state": str(auth_data["state"]),
        }
        self._logger.info("registration_submitted", email=context.email)
        return StepResult(success=True, data={"metadata": new_metadata})
