"""Usage statistics API routes."""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.config.settings import load_settings
from src.storage.stats_store import StatsStore

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _build_store() -> StatsStore:
    settings = load_settings()
    return StatsStore(settings.storage.stats_db_path)


@router.get("/summary")
def get_summary() -> dict:
    return _build_store().get_today_summary()


@router.get("/hourly")
def get_hourly(date: str | None = None) -> list[dict]:
    return _build_store().get_hourly_stats(date)


@router.get("/daily")
def get_daily(days: int = Query(7, ge=1, le=90)) -> list[dict]:
    return _build_store().get_daily_stats(days)


@router.get("/models")
def get_model_distribution() -> list[dict]:
    return _build_store().get_model_distribution()


@router.get("/accounts")
def get_account_usage() -> list[dict]:
    return _build_store().get_account_usage()
