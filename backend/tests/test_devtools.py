"""Tests for devtools modules and related APIs."""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from src.middleware.auth import AdminContext, require_admin_token
from src.pipeline.base import Pipeline, Step, StepResult
from src.pipeline.context import PipelineContext
from src.pipeline.runner import PipelineRunner
from src.utils.log_collector import LogCollector


class _DummyStep(Step):
    name = "dummy"
    description = "dummy"

    async def execute(self, context: PipelineContext) -> StepResult:
        return StepResult(success=True, data={"email": "event@example.com"})


class _FakeManager:
    async def start(self, test_file: str | None) -> str:
        self._last_test_file = test_file
        return "run-test-1"


class DevToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[require_admin_token] = lambda: AdminContext(username="test-admin")
        self.client = TestClient(app)
        self.collector = LogCollector()
        self.collector.clear()
        self._old_log_dir = self.collector._log_dir
        self._old_subscribers = set(self.collector._subscribers)

    def tearDown(self) -> None:
        self.collector.clear()
        self.collector._subscribers = self._old_subscribers
        self.collector._log_dir = self._old_log_dir
        app.dependency_overrides.pop(require_admin_token, None)

    def test_log_file_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            self.collector._log_dir = Path(tempdir)
            self.collector._log_dir.mkdir(parents=True, exist_ok=True)

            self.collector.add("INFO", "persisted", source="devtools")

            files = self.collector.list_log_files()
            self.assertEqual(len(files), 1)
            log_file = self.collector._log_dir / files[0]
            self.assertTrue(log_file.exists())

            rows = log_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(rows), 1)
            item = json.loads(rows[0])
            self.assertEqual(item["level"], "INFO")
            self.assertEqual(item["source"], "devtools")
            self.assertEqual(item["message"], "persisted")

    def test_log_subscriber_receives_events(self) -> None:
        received: list[dict] = []

        def callback(item: dict) -> None:
            received.append(item)

        self.collector.add_subscriber(callback)
        self.collector.add("ERROR", "subscriber event", source="ws")
        self.collector.remove_subscriber(callback)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["message"], "subscriber event")

    def test_pipeline_events_emitted(self) -> None:
        events: list[dict] = []
        runner = PipelineRunner(max_retries=1, retry_delay=0)
        pipeline = Pipeline("test_pipeline", "desc", [_DummyStep()])

        async def callback(event: dict[str, object]) -> None:
            events.append(event)

        asyncio.run(runner.run(pipeline, PipelineContext(), event_callback=callback))

        event_names = [item["event"] for item in events]
        self.assertEqual(event_names, ["pipeline_start", "step_start", "step_end", "pipeline_end"])
        self.assertEqual(events[2]["status"], "success")

    def test_test_runner_api(self) -> None:
        fake_manager = _FakeManager()
        with patch("api.devtools.get_test_manager", return_value=fake_manager):
            response = self.client.post("/api/devtools/test", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "started")
        self.assertEqual(payload["run_id"], "run-test-1")

    def test_log_history_api(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            self.collector._log_dir = Path(tempdir)
            self.collector._log_dir.mkdir(parents=True, exist_ok=True)
            self.collector.add("INFO", "history line", source="history")

            files_response = self.client.get("/api/devtools/logs/files")
            self.assertEqual(files_response.status_code, 200)
            files = files_response.json()["files"]
            self.assertEqual(len(files), 1)

            history_response = self.client.get(
                "/api/devtools/logs/history",
                params={"file": files[0], "offset": 0, "limit": 100},
            )
            self.assertEqual(history_response.status_code, 200)
            items = history_response.json()["items"]
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["message"], "history line")


if __name__ == "__main__":
    unittest.main()
