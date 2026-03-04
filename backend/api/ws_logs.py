"""WebSocket route for real-time runtime logs."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.utils.log_collector import LogCollector

router = APIRouter()


def _passes_filter(item: dict[str, Any], filters: dict[str, str]) -> bool:
    level = filters.get("level")
    source = filters.get("source")
    search = filters.get("search")

    if level and item.get("level") != level.upper():
        return False
    if source and item.get("source") != source:
        return False
    if search and search.lower() not in str(item.get("message", "")).lower():
        return False
    return True


@router.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket) -> None:
    token = (websocket.query_params.get("token") or "").strip()
    if not token:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    collector = LogCollector()
    send_lock = asyncio.Lock()
    filters: dict[str, str] = {}

    async def on_log(item: dict[str, Any]) -> None:
        if not _passes_filter(item, filters):
            return
        async with send_lock:
            await websocket.send_json(item)

    collector.add_subscriber(on_log)
    try:
        while True:
            text = await websocket.receive_text()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            filters = {
                "level": str(payload.get("level") or "").strip(),
                "source": str(payload.get("source") or "").strip(),
                "search": str(payload.get("search") or "").strip(),
            }
    except WebSocketDisconnect:
        pass
    finally:
        collector.remove_subscriber(on_log)
