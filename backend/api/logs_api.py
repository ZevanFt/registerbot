"""Runtime logs query and maintenance API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.utils.log_collector import LogCollector
from src.middleware.auth import require_operator_permission, require_viewer_permission

router = APIRouter(
    prefix="/api/logs",
    tags=["logs"],
    dependencies=[Depends(require_viewer_permission)],
)


@router.get("")
def get_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    level: str | None = None,
    source: str | None = None,
    search: str | None = None,
) -> dict:
    collector = LogCollector()
    return collector.list(page=page, limit=limit, level=level, source=source, search=search)


@router.delete("")
def clear_logs(_=Depends(require_operator_permission)) -> dict[str, str]:
    collector = LogCollector()
    collector.clear()
    return {"status": "cleared"}
