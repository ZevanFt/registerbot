"""Upgrade plan step placeholder."""

from __future__ import annotations

from src.pipeline.base import Step, StepResult
from src.pipeline.context import PipelineContext


class UpgradePlusStep(Step):
    """Upgrade account to Plus plan."""

    name = "upgrade_plus"
    description = "Upgrade account plan"

    async def execute(self, context: PipelineContext) -> StepResult:
        settings = context.get("settings")
        if settings is None:
            return StepResult(success=False, error="Settings missing in context metadata")

        if settings.registration.skip_upgrade_plus:
            return StepResult(success=True, skip_reason="skip_upgrade_plus enabled")
        return StepResult(success=False, error="Upgrade Plus requires manual completion")
