"""SQLite-backed token management store."""

from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog


class TokenStore:
    """Create, list, revoke, and delete API tokens."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._logger = structlog.get_logger("TokenStore")
        self._init_db()

    def _init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    key TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    total_requests INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0
                )
                """
            )
            conn.commit()

    def create_token(self, name: str) -> dict[str, Any]:
        key = "sk-" + secrets.token_hex(16)
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO tokens (name, key, created_at) VALUES (?, ?, ?)",
                (name, key, now),
            )
            conn.commit()
            token_id = cursor.lastrowid
        return {
            "id": token_id,
            "name": name,
            "key": key,
            "created_at": now,
            "last_used_at": None,
            "is_active": True,
            "total_requests": 0,
            "total_tokens": 0,
        }

    def list_tokens(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM tokens ORDER BY id DESC").fetchall()
        return [self._row_to_dict(row) for row in rows]

    def revoke_token(self, token_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("UPDATE tokens SET is_active = 0 WHERE id = ?", (token_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_active_token_by_key(self, key: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM tokens WHERE key = ? AND is_active = 1 LIMIT 1",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def update_usage(self, token_id: int, request_inc: int = 1, token_inc: int = 0) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE tokens
                SET total_requests = total_requests + ?,
                    total_tokens = total_tokens + ?,
                    last_used_at = ?
                WHERE id = ?
                """,
                (request_inc, token_inc, now, token_id),
            )
            conn.commit()

    def delete_token(self, token_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM tokens WHERE id = ?", (token_id,))
            conn.commit()
            return cursor.rowcount > 0

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["is_active"] = bool(data.get("is_active", 0))
        return data
