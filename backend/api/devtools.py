"""DevTools API routes for test runs and log archive access."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel

from src.utils.log_collector import LogCollector

api_router = APIRouter(prefix="/api/devtools", tags=["devtools"])
ws_router = APIRouter()


class TestRunRequest(BaseModel):
    test_file: str | None = None


class TestRunManager:
    """Manage async pytest runs and stream output to subscribers."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._last_run: dict[str, Any] = {"run_id": None, "status": "idle", "output": []}
        self._current_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def start(self, test_file: str | None) -> str:
        async with self._lock:
            if self._current_task and not self._current_task.done():
                raise RuntimeError("A test run is already in progress")

            run_id = uuid.uuid4().hex
            self._last_run = {"run_id": run_id, "status": "running", "output": []}
            self._current_task = asyncio.create_task(self._run_pytest(run_id=run_id, test_file=test_file))
            return run_id

    async def get_last(self) -> dict[str, Any]:
        async with self._lock:
            return {
                "run_id": self._last_run.get("run_id"),
                "status": self._last_run.get("status"),
                "output": [dict(item) for item in self._last_run.get("output", [])],
            }

    async def _run_pytest(self, run_id: str, test_file: str | None) -> None:
        cmd = [".venv/bin/python", "-m", "pytest", "tests/", "-v", "--tb=short"]
        if test_file:
            cmd = [".venv/bin/python", "-m", "pytest", test_file, "-v", "--tb=short"]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async def read_stream(stream: asyncio.StreamReader | None, stream_type: str) -> None:
            if stream is None:
                return
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip("\r\n")
                await self._publish({"type": stream_type, "line": text, "run_id": run_id})

        await asyncio.gather(read_stream(process.stdout, "stdout"), read_stream(process.stderr, "stderr"))
        exit_code = await process.wait()
        summary = f"pytest finished with exit_code={exit_code}"
        await self._publish(
            {
                "type": "exit",
                "exit_code": exit_code,
                "summary": summary,
                "run_id": run_id,
            }
        )

        async with self._lock:
            if self._last_run.get("run_id") == run_id:
                self._last_run["status"] = "finished"

    async def _publish(self, event: dict[str, Any]) -> None:
        async with self._lock:
            self._last_run.setdefault("output", []).append(dict(event))
            clients = list(self._clients)

        stale_clients: list[WebSocket] = []
        for client in clients:
            try:
                await client.send_json(event)
            except Exception:
                stale_clients.append(client)

        if stale_clients:
            async with self._lock:
                for client in stale_clients:
                    self._clients.discard(client)


_test_run_manager = TestRunManager()


def get_test_manager() -> TestRunManager:
    return _test_run_manager


def _validate_test_file(test_file: str | None) -> str | None:
    if not test_file:
        return None
    path = Path(test_file)
    if path.is_absolute():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="test_file must be a relative path")
    resolved = path.resolve()
    tests_root = Path("tests").resolve()
    if tests_root not in resolved.parents and resolved != tests_root:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="test_file must be under tests/")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="test_file does not exist")
    return str(path)


@api_router.post("/test")
async def start_test_run(payload: TestRunRequest) -> dict[str, str]:
    validated_file = _validate_test_file(payload.test_file)
    manager = get_test_manager()
    try:
        run_id = await manager.start(validated_file)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {"run_id": run_id, "status": "started"}


@api_router.get("/test/last")
async def get_last_test_run() -> dict[str, Any]:
    manager = get_test_manager()
    return await manager.get_last()


@api_router.get("/logs/files")
def list_log_files() -> dict[str, list[str]]:
    collector = LogCollector()
    return {"files": collector.list_log_files()}


@api_router.get("/logs/history")
def read_log_history(
    file: str = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    collector = LogCollector()
    try:
        items = collector.read_log_file(file, offset=offset, limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"items": items, "file": file, "offset": offset, "limit": limit}


@ws_router.websocket("/ws/test")
async def ws_test(websocket: WebSocket) -> None:
    token = (websocket.query_params.get("token") or "").strip()
    if not token:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    manager = get_test_manager()
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
