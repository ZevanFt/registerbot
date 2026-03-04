"""SQLite-backed usage statistics queries."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class StatsStore:
    """Read aggregate usage statistics from usage log records."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    account_id INTEGER,
                    model TEXT,
                    request_tokens INTEGER DEFAULT 0,
                    response_tokens INTEGER DEFAULT 0,
                    status_code INTEGER DEFAULT 200
                )
                """
            )
            conn.commit()

    def get_today_summary(self) -> dict[str, Any]:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) as total_requests, COALESCE(SUM(request_tokens + response_tokens), 0) as total_tokens FROM usage_logs WHERE timestamp LIKE ?",
                (f"{today}%",),
            ).fetchone()
        return {"total_requests": row[0], "total_tokens": row[1], "avg_latency": 0}

    def append_usage_log(
        self,
        timestamp: str,
        account_id: int | None,
        model: str | None,
        request_tokens: int,
        response_tokens: int,
        status_code: int,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO usage_logs (
                    timestamp,
                    account_id,
                    model,
                    request_tokens,
                    response_tokens,
                    status_code
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (timestamp, account_id, model, request_tokens, response_tokens, status_code),
            )
            conn.commit()

    def get_hourly_stats(self, date: str | None = None) -> list[dict[str, Any]]:
        if not date:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        result: list[dict[str, Any]] = []
        with sqlite3.connect(self.db_path) as conn:
            for hour in range(24):
                prefix = f"{date}T{hour:02d}"
                row = conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(request_tokens + response_tokens), 0) FROM usage_logs WHERE timestamp LIKE ?",
                    (f"{prefix}%",),
                ).fetchone()
                result.append({"hour": hour, "requests": row[0], "tokens": row[1]})
        return result

    def get_daily_stats(self, days: int = 7) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        with sqlite3.connect(self.db_path) as conn:
            for index in range(days - 1, -1, -1):
                date = (now - timedelta(days=index)).strftime("%Y-%m-%d")
                row = conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(request_tokens + response_tokens), 0) FROM usage_logs WHERE timestamp LIKE ?",
                    (f"{date}%",),
                ).fetchone()
                result.append({"date": date, "requests": row[0], "tokens": row[1]})
        return result

    def get_model_distribution(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT model, COUNT(*) as count FROM usage_logs WHERE model IS NOT NULL GROUP BY model ORDER BY count DESC"
            ).fetchall()
        total = sum(row[1] for row in rows) or 1
        return [
            {"model": row[0], "count": row[1], "percentage": round(row[1] / total * 100, 1)}
            for row in rows
        ]

    def get_account_usage(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT account_id, COUNT(*) as requests, COALESCE(SUM(request_tokens + response_tokens), 0) as tokens FROM usage_logs WHERE account_id IS NOT NULL GROUP BY account_id ORDER BY requests DESC"
            ).fetchall()
        return [{"account_id": row[0], "requests": row[1], "tokens": row[2]} for row in rows]
