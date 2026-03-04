"""Pipeline runner implementation with retry support."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from .base import Pipeline, Step, StepResult
from .context import PipelineContext

PipelineEventCallback = Callable[[dict[str, object]], Awaitable[None]]


@dataclass(frozen=True)
class PipelineResult:
    """Aggregate result for one pipeline run."""

    success: bool
    steps_completed: int
    steps_failed: int
    results: dict[str, StepResult] = field(default_factory=dict)
    total_duration: float = 0.0


class PipelineRunner:
    """Run pipeline steps sequentially with retries."""

    def __init__(self, max_retries: int = 3, retry_delay: float = 5.0) -> None:
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._logger = structlog.get_logger(self.__class__.__name__)

    async def run(
        self,
        pipeline: Pipeline,
        context: PipelineContext,
        event_callback: PipelineEventCallback | None = None,
    ) -> PipelineResult:
        """Run a pipeline and return aggregate result."""

        start = time.monotonic()
        current_context = context
        results: dict[str, StepResult] = {}
        completed = 0
        failed = 0
        total_steps = len(pipeline.steps)

        await self._emit_event(
            event_callback,
            event="pipeline_start",
            step_name="",
            step_index=0,
            total_steps=total_steps,
            status="running",
            duration_ms=0,
            error=None,
        )

        for index, step in enumerate(pipeline.steps, start=1):
            await self._emit_event(
                event_callback,
                event="step_start",
                step_name=step.name,
                step_index=index,
                total_steps=total_steps,
                status="running",
                duration_ms=0,
                error=None,
            )
            step_started = time.monotonic()
            step_result = await self._run_step_with_retries(step, current_context)
            results[step.name] = step_result
            step_duration_ms = int((time.monotonic() - step_started) * 1000)
            step_status = "success" if step_result.success else "failed"
            if step_result.skip_reason:
                step_status = "skipped"
            await self._emit_event(
                event_callback,
                event="step_end",
                step_name=step.name,
                step_index=index,
                total_steps=total_steps,
                status=step_status,
                duration_ms=step_duration_ms,
                error=step_result.error,
            )
            if step_result.success:
                completed += 1
                if step_result.data:
                    for key, value in step_result.data.items():
                        current_context = current_context.set(key, value)
                continue
            failed += 1
            self._logger.error("pipeline_step_failed", step=step.name, error=step_result.error)
            break

        total_duration = time.monotonic() - start
        await self._emit_event(
            event_callback,
            event="pipeline_end",
            step_name="",
            step_index=total_steps,
            total_steps=total_steps,
            status="success" if failed == 0 else "failed",
            duration_ms=int(total_duration * 1000),
            error=None if failed == 0 else "pipeline_failed",
        )
        return PipelineResult(
            success=failed == 0,
            steps_completed=completed,
            steps_failed=failed,
            results=results,
            total_duration=total_duration,
        )

    async def run_step(self, step: Step, context: PipelineContext) -> StepResult:
        """Run one step once."""

        if not step.validate(context):
            return StepResult(success=False, error=f"Validation failed for step: {step.name}")

        started = time.monotonic()
        result = await step.execute(context)
        if result.duration > 0:
            return result
        duration = time.monotonic() - started
        return StepResult(
            success=result.success,
            data=result.data,
            error=result.error,
            skip_reason=result.skip_reason,
            duration=duration,
        )

    async def _run_step_with_retries(self, step: Step, context: PipelineContext) -> StepResult:
        """Run one step with retry loop."""

        last_result = StepResult(success=False, error=f"Step {step.name} did not run")
        for attempt in range(1, self.max_retries + 1):
            last_result = await self.run_step(step, context)
            if last_result.success:
                return last_result
            if attempt < self.max_retries:
                self._logger.warning("step_retry", step=step.name, attempt=attempt)
                await asyncio.sleep(self.retry_delay)
        return last_result

    async def _emit_event(
        self,
        event_callback: PipelineEventCallback | None,
        *,
        event: str,
        step_name: str,
        step_index: int,
        total_steps: int,
        status: str,
        duration_ms: int,
        error: str | None,
    ) -> None:
        if event_callback is None:
            return
        payload: dict[str, object] = {
            "event": event,
            "step_name": step_name,
            "step_index": step_index,
            "total_steps": total_steps,
            "status": status,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if error:
            payload["error"] = error
        await event_callback(payload)
