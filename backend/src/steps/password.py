"""Password setup step placeholder."""

from __future__ import annotations

import structlog

from src.integrations.openai_api import OpenAIRegistrationClient
from src.pipeline.base import Step, StepResult
from src.pipeline.context import PipelineContext


class SetPasswordStep(Step):
    """Set account password after verification."""

    name = "set_password"
    description = "Set OpenAI account password"

    def __init__(self) -> None:
        self._logger = structlog.get_logger(self.__class__.__name__)

    async def execute(self, context: PipelineContext) -> StepResult:
        settings = context.get("settings")
        if settings is None:
            return StepResult(success=False, error="Settings missing in context metadata")

        # If access_token was already extracted (e.g. from browser session), skip token exchange
        if context.access_token:
            self._logger.info("token_exchange_skipped", reason="access_token already present")
            return StepResult(
                success=True,
                skip_reason="access_token already available from browser session",
                data={},
            )

        authorization_code = str(context.get("authorization_code", ""))
        if not authorization_code:
            return StepResult(success=False, error="authorization_code missing in context")
        code_verifier = str(context.metadata.get("code_verifier", ""))
        if not code_verifier:
            return StepResult(success=False, error="code_verifier missing in metadata")

        # Derive token base URL from token_url setting
        # e.g. "https://auth0.openai.com/oauth/token" -> "https://auth0.openai.com"
        token_url = settings.openai.token_url
        token_base = (
            token_url.rsplit("/oauth/token", 1)[0]
            if "/oauth/token" in token_url
            else settings.openai.auth_url
        )

        client = OpenAIRegistrationClient(
            auth_url=settings.openai.auth_url,
            oauth_client_id=settings.openai.oauth_client_id,
            timeout=settings.openai.timeout_seconds,
            proxy=settings.network.openai_proxy or settings.network.http_proxy,
        )
        try:
            token_payload = await client.exchange_code_for_tokens(
                authorization_code=authorization_code,
                code_verifier=code_verifier,
                redirect_uri=settings.openai.register_callback_url,
                auth_url=token_base,
            )
        except Exception as exc:  # noqa: BLE001
            return StepResult(success=False, error=f"set_password_failed: {exc}")

        access_token = str(token_payload.get("access_token", ""))
        refresh_token = str(token_payload.get("refresh_token", ""))
        expires_in = int(token_payload.get("expires_in", 0))
        if not access_token:
            return StepResult(success=False, error="set_password_failed: missing access_token")

        self._logger.info("oauth_tokens_exchanged", email=context.email)
        return StepResult(
            success=True,
            data={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": expires_in,
            },
        )
