"""Pipeline events WebSocket and latest event API."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from src.middleware.auth import require_admin_permission

ws_router = APIRouter()
api_router = APIRouter(
    prefix="/api/devtools",
    tags=["devtools"],
    dependencies=[Depends(require_admin_permission)],
)


class PipelineEventHub:
    """Broadcast pipeline events and keep latest run in memory."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._last_events: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def emit(self, event: dict[str, Any]) -> None:
        async with self._lock:
            event_name = str(event.get("event") or "")
            if event_name == "pipeline_start":
                self._last_events = [dict(event)]
            else:
                self._last_events.append(dict(event))
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

    async def get_last_events(self) -> list[dict[str, Any]]:
        async with self._lock:
            return [dict(item) for item in self._last_events]


_pipeline_event_hub = PipelineEventHub()


def get_pipeline_event_hub() -> PipelineEventHub:
    return _pipeline_event_hub


@ws_router.websocket("/ws/pipeline")
async def ws_pipeline(websocket: WebSocket) -> None:
    token = (websocket.query_params.get("token") or "").strip()
    if not token:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    hub = get_pipeline_event_hub()
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(websocket)


@api_router.get("/pipeline/last")
async def get_last_pipeline_events() -> dict[str, list[dict[str, Any]]]:
    hub = get_pipeline_event_hub()
    return {"events": await hub.get_last_events()}
