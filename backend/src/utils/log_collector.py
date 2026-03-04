"""Thread-safe log collector with in-memory buffer and file persistence."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

SubscriberCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class LogCollector:
    """Collect and query runtime logs with memory and file storage."""

    _instance: "LogCollector | None" = None

    def __new__(cls) -> "LogCollector":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._logs = []
            cls._instance._counter = 0
            cls._instance._lock = Lock()
            cls._instance._subscribers = set()
            cls._instance._log_dir = Path("data/logs")
            cls._instance._log_dir.mkdir(parents=True, exist_ok=True)
            cls._instance._logger = logging.getLogger(__name__)
        return cls._instance

    def add(self, level: str, message: str, source: str = "system", metadata: dict | None = None) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.upper(),
            "source": source,
            "message": message,
            "metadata": metadata or {},
        }
        with self._lock:
            self._counter += 1
            item = {"id": self._counter, **event}
            self._logs.append(item)
            if len(self._logs) > 1000:
                self._logs = self._logs[-1000:]
            subscribers = list(self._subscribers)

        self._append_file(event)
        self._notify_subscribers(item, subscribers)

    def list(
        self,
        page: int = 1,
        limit: int = 50,
        level: str | None = None,
        source: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            filtered = list(self._logs)
        if level:
            filtered = [item for item in filtered if item["level"] == level.upper()]
        if source:
            filtered = [item for item in filtered if item["source"] == source]
        if search:
            filtered = [item for item in filtered if search.lower() in item["message"].lower()]
        filtered.reverse()
        total = len(filtered)
        start = (page - 1) * limit
        return {"items": filtered[start : start + limit], "total": total}

    def add_subscriber(self, callback: SubscriberCallback) -> None:
        with self._lock:
            self._subscribers.add(callback)

    def remove_subscriber(self, callback: SubscriberCallback) -> None:
        with self._lock:
            self._subscribers.discard(callback)

    def list_log_files(self) -> list[str]:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        files = [path.name for path in self._log_dir.glob("*.jsonl") if path.is_file()]
        files.sort(reverse=True)
        return files

    def read_log_file(self, filename: str, offset: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        if "/" in filename or "\\" in filename or not filename.endswith(".jsonl"):
            raise ValueError("Invalid filename")
        if offset < 0:
            raise ValueError("offset must be >= 0")
        if limit <= 0:
            raise ValueError("limit must be > 0")
        path = self._log_dir / filename
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(filename)

        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as fh:
            for idx, line in enumerate(fh):
                if idx < offset:
                    continue
                if len(rows) >= limit:
                    break
                text = line.strip()
                if not text:
                    continue
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    self._logger.exception("log_file_json_decode_failed", extra={"filename": filename})
                    continue
                if isinstance(parsed, dict):
                    rows.append(parsed)
        return rows

    def clear(self) -> None:
        with self._lock:
            self._logs.clear()
            self._counter = 0

    def _append_file(self, event: dict[str, Any]) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        filename = datetime.now(timezone.utc).strftime("%Y-%m-%d.jsonl")
        path = self._log_dir / filename
        try:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=True))
                fh.write("\n")
        except OSError:
            self._logger.exception("log_file_write_failed", extra={"path": str(path)})

    def _notify_subscribers(self, item: dict[str, Any], subscribers: list[SubscriberCallback]) -> None:
        for callback in subscribers:
            try:
                result = callback(item)
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        self._logger.error("subscriber_coroutine_without_event_loop")
                        continue
                    loop.create_task(result)
            except Exception:
                self._logger.exception("log_subscriber_callback_failed")
