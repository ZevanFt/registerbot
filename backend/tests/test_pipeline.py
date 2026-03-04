"""Tests for pipeline primitives and runner behavior."""

from __future__ import annotations

import unittest

from src.pipeline.base import Pipeline, Step, StepResult
from src.pipeline.context import PipelineContext
from src.pipeline.runner import PipelineRunner


class DummySuccessStep(Step):
    name = "dummy_success"
    description = "A successful step"

    async def execute(self, context: PipelineContext) -> StepResult:
        return StepResult(success=True, data={"email": "user@example.com"})


class DummyFailStep(Step):
    name = "dummy_fail"
    description = "A failing step"

    async def execute(self, context: PipelineContext) -> StepResult:
        return StepResult(success=False, error="boom")


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_context_is_immutable(self) -> None:
        ctx = PipelineContext()
        new_ctx = ctx.set("email", "a@b.com")
        self.assertIsNone(ctx.email)
        self.assertEqual(new_ctx.email, "a@b.com")

    async def test_runner_runs_pipeline_successfully(self) -> None:
        runner = PipelineRunner(max_retries=1, retry_delay=0)
        pipeline = Pipeline("p", "desc", [DummySuccessStep()])
        result = await runner.run(pipeline, PipelineContext())
        self.assertTrue(result.success)
        self.assertEqual(result.steps_completed, 1)
        self.assertEqual(result.steps_failed, 0)

    async def test_runner_stops_on_failure(self) -> None:
        runner = PipelineRunner(max_retries=1, retry_delay=0)
        pipeline = Pipeline("p", "desc", [DummyFailStep(), DummySuccessStep()])
        result = await runner.run(pipeline, PipelineContext())
        self.assertFalse(result.success)
        self.assertEqual(result.steps_completed, 0)
        self.assertEqual(result.steps_failed, 1)


if __name__ == "__main__":
    unittest.main()
