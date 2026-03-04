"""Email-related steps backed by TalentMail integration."""

from __future__ import annotations

import structlog

from src.integrations.talentmail import TalentMailClient
from src.pipeline.base import Step, StepResult
from src.pipeline.context import PipelineContext


class CreateTempEmailStep(Step):
    """Create a temporary mailbox for registration."""

    name = "create_temp_email"
    description = "Create temp mailbox through TalentMail"

    def __init__(self) -> None:
        self._logger = structlog.get_logger(self.__class__.__name__)

    async def execute(self, context: PipelineContext) -> StepResult:
        settings = context.get("settings")
        if settings is None:
            return StepResult(success=False, error="Settings missing in context metadata")

        client = TalentMailClient(
            base_url=settings.talentmail.base_url,
            email=settings.talentmail.email,
            password=settings.talentmail.password,
            proxy=settings.network.talentmail_proxy or settings.network.http_proxy,
        )
        mailbox = await client.create_temp_email()
        mailbox_id = str(mailbox.get("id") or mailbox.get("mailbox_id") or "")
        email = mailbox.get("email")
        if not mailbox_id or not email:
            return StepResult(success=False, error="TalentMail response missing mailbox id or email")

        self._logger.info("temp_email_created", mailbox_id=mailbox_id, email=email)
        return StepResult(success=True, data={"mailbox_id": mailbox_id, "email": email})


class WaitForVerificationCodeStep(Step):
    """Poll mailbox until verification code appears."""

    name = "wait_for_verification_code"
    description = "Wait for OpenAI verification email code"

    def __init__(self, timeout: int = 300, poll_interval: int = 5) -> None:
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._logger = structlog.get_logger(self.__class__.__name__)

    def validate(self, context: PipelineContext) -> bool:
        return bool(context.mailbox_id)

    async def execute(self, context: PipelineContext) -> StepResult:
        settings = context.get("settings")
        if settings is None:
            return StepResult(success=False, error="Settings missing in context metadata")
        if not context.mailbox_id:
            return StepResult(success=False, error="mailbox_id missing in context")

        client = TalentMailClient(
            base_url=settings.talentmail.base_url,
            email=settings.talentmail.email,
            password=settings.talentmail.password,
            proxy=settings.network.talentmail_proxy or settings.network.http_proxy,
        )
        code = await client.wait_for_code(
            mailbox_id=context.mailbox_id,
            timeout=self.timeout,
            poll_interval=self.poll_interval,
        )
        self._logger.info("verification_code_received", mailbox_id=context.mailbox_id)
        return StepResult(success=True, data={"verification_code": code})
