"""SQLite-backed admin user storage."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils.passwords import hash_password, verify_password


class UserStore:
    """Store and verify dashboard users."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT UNIQUE,
                    password_hash TEXT NOT NULL,
                    permission TEXT NOT NULL DEFAULT 'admin',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login_at TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_permission ON users(permission)")
            conn.commit()

    def ensure_admin_user(self, username: str, password: str, email: str | None = None) -> None:
        """Create initial admin user if not exists."""

        clean_username = username.strip()
        if not clean_username:
            return

        if self.find_by_username(clean_username) is not None:
            return

        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO users (
                    username, email, password_hash, permission, is_active, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_username,
                    email.strip() if isinstance(email, str) and email.strip() else None,
                    hash_password(password),
                    "admin",
                    1,
                    now,
                    now,
                ),
            )
            conn.commit()

    def find_by_username(self, username: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM users WHERE lower(username) = lower(?) LIMIT 1",
                (username,),
            ).fetchone()
        return dict(row) if row is not None else None

    def find_by_username_or_email(self, identifier: str) -> dict[str, Any] | None:
        clean = identifier.strip()
        if not clean:
            return None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM users
                WHERE lower(username) = lower(?)
                   OR (email IS NOT NULL AND lower(email) = lower(?))
                LIMIT 1
                """,
                (clean, clean),
            ).fetchone()
        return dict(row) if row is not None else None

    def verify_credentials(self, identifier: str, password: str) -> dict[str, Any] | None:
        user = self.find_by_username_or_email(identifier)
        if user is None:
            return None
        if int(user.get("is_active") or 0) != 1:
            return None
        if not verify_password(password, str(user.get("password_hash") or "")):
            return None
        self._touch_last_login(int(user["id"]))
        user["last_login_at"] = datetime.now(timezone.utc).isoformat()
        return user

    def _touch_last_login(self, user_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
                (now, now, user_id),
            )
            conn.commit()

    def list_users(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    id, username, email, permission, is_active,
                    created_at, updated_at, last_login_at
                FROM users
                ORDER BY id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def create_user(
        self,
        *,
        username: str,
        password: str,
        permission: str,
        email: str | None = None,
        is_active: bool = True,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (
                    username, email, password_hash, permission, is_active, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    username.strip(),
                    email.strip() if isinstance(email, str) and email.strip() else None,
                    hash_password(password),
                    permission.strip(),
                    1 if is_active else 0,
                    now,
                    now,
                ),
            )
            conn.commit()
        return int(cursor.lastrowid)

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT
                    id, username, email, permission, is_active,
                    created_at, updated_at, last_login_at
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def update_user(
        self,
        user_id: int,
        *,
        permission: str | None = None,
        email: str | None = None,
        is_active: bool | None = None,
    ) -> bool:
        values: dict[str, Any] = {}
        if permission is not None:
            values["permission"] = permission.strip()
        if email is not None:
            values["email"] = email.strip() or None
        if is_active is not None:
            values["is_active"] = 1 if is_active else 0
        if not values:
            return False

        values["updated_at"] = datetime.now(timezone.utc).isoformat()
        columns = ", ".join(f"{key} = ?" for key in values)
        params = list(values.values()) + [user_id]
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f"UPDATE users SET {columns} WHERE id = ?", params)
            conn.commit()
        return cursor.rowcount > 0

    def reset_password(self, user_id: int, new_password: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (hash_password(new_password), now, user_id),
            )
            conn.commit()
        return cursor.rowcount > 0
