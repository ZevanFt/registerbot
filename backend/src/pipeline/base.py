"""Pipeline primitives: step contract, result model, and pipeline container."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .context import PipelineContext


class StepStatus(str, Enum):
    """Execution status of one step."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class StepResult:
    """Step execution result."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    skip_reason: str | None = None
    duration: float = 0.0


class Step(ABC):
    """Abstract step interface used by pipeline runner."""

    name: str = "base_step"
    description: str = "Base pipeline step"

    @abstractmethod
    async def execute(self, context: PipelineContext) -> StepResult:
        """Execute the step logic."""

    async def rollback(self, context: PipelineContext) -> None:
        """Rollback side effects when needed."""

        return None

    def validate(self, context: PipelineContext) -> bool:
        """Validate if step can run under current context."""

        return True


@dataclass(frozen=True)
class Pipeline:
    """Pipeline declaration."""

    name: str
    description: str
    steps: list[Step]
