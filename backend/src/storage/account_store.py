"""SQLite-backed account storage with encrypted password fields."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from src.utils.crypto import decrypt_text, encrypt_text


class AccountStore:
    """Store and retrieve OpenAI account records."""

    def __init__(self, db_path: str, encryption_key: str) -> None:
        self.db_path = db_path
        self.encryption_key = encryption_key
        self._logger = structlog.get_logger(self.__class__.__name__)
        self._init_db()

    def _init_db(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    password_encrypted TEXT NOT NULL,
                    phone TEXT,
                    openai_token TEXT,
                    plan TEXT DEFAULT 'free',
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS account_health (
                    account_id INTEGER PRIMARY KEY,
                    runtime_status TEXT NOT NULL DEFAULT 'active',
                    consecutive_failures INTEGER NOT NULL DEFAULT 0,
                    total_failures INTEGER NOT NULL DEFAULT 0,
                    cooldown_until TEXT,
                    last_check_at TEXT,
                    last_success_at TEXT,
                    last_failure_at TEXT,
                    last_failure_reason TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_account_health_status
                ON account_health(runtime_status, cooldown_until)
                """
            )
            migration_columns = [
                ("refresh_token", "TEXT"),
                ("token_expires_at", "TEXT"),
                ("token_last_refreshed_at", "TEXT"),
                ("token_status", "TEXT NOT NULL DEFAULT 'unknown'"),
                ("token_refresh_error", "TEXT"),
                ("token_refresh_attempts", "INTEGER NOT NULL DEFAULT 0"),
            ]
            for column, definition in migration_columns:
                try:
                    conn.execute(f"ALTER TABLE accounts ADD COLUMN {column} {definition}")
                except sqlite3.OperationalError as exc:
                    if "duplicate column name" not in str(exc).lower():
                        raise
            conn.commit()

    def save_account(self, account_info: dict[str, Any]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        password = str(account_info.get("password", ""))
        encrypted = self._encrypt(password)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.execute(
                """
                INSERT INTO accounts (
                    email, password_encrypted, phone, openai_token, refresh_token, token_expires_at,
                    token_last_refreshed_at, token_status, token_refresh_error, token_refresh_attempts,
                    plan, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_info.get("email", ""),
                    encrypted,
                    account_info.get("phone"),
                    account_info.get("openai_token"),
                    account_info.get("refresh_token"),
                    account_info.get("token_expires_at"),
                    account_info.get("token_last_refreshed_at"),
                    account_info.get("token_status", "unknown"),
                    account_info.get("token_refresh_error"),
                    int(account_info.get("token_refresh_attempts") or 0),
                    account_info.get("plan", "free"),
                    account_info.get("status", "pending"),
                    now,
                    now,
                ),
            )
            conn.commit()
            account_id = int(cursor.lastrowid)
        self.ensure_health_record(account_id)
        self._logger.info("account_saved", account_id=account_id)
        return account_id

    def get_account(self, account_id: int) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["password"] = self._decrypt(result.pop("password_encrypted"))
        return result

    def list_accounts(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM accounts ORDER BY id DESC").fetchall()
        accounts: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["password"] = self._decrypt(item.pop("password_encrypted"))
            accounts.append(item)
        return accounts

    def update_account(self, account_id: int, updates: dict[str, Any]) -> bool:
        if not updates:
            return False

        allowed = {
            "email",
            "password",
            "phone",
            "openai_token",
            "refresh_token",
            "token_expires_at",
            "token_last_refreshed_at",
            "token_status",
            "token_refresh_error",
            "token_refresh_attempts",
            "plan",
            "status",
        }
        values: dict[str, Any] = {}
        for key, value in updates.items():
            if key in allowed:
                values[key] = value
        if not values:
            return False

        if "password" in values:
            values["password_encrypted"] = self._encrypt(str(values.pop("password")))
        values["updated_at"] = datetime.now(timezone.utc).isoformat()

        columns = ", ".join(f"{key} = ?" for key in values)
        params = list(values.values()) + [account_id]
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f"UPDATE accounts SET {columns} WHERE id = ?", params)
            conn.commit()
            updated = cursor.rowcount > 0
        return updated

    def delete_account(self, account_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
        return deleted

    def ensure_health_record(self, account_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO account_health (account_id, updated_at)
                VALUES (?, ?)
                """,
                (account_id, now),
            )
            conn.commit()

    def get_health(self, account_id: int) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM account_health WHERE account_id = ?",
                (account_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def update_health(self, account_id: int, **fields: Any) -> None:
        if not fields:
            return
        self.ensure_health_record(account_id)
        allowed = {
            "runtime_status",
            "consecutive_failures",
            "total_failures",
            "cooldown_until",
            "last_check_at",
            "last_success_at",
            "last_failure_at",
            "last_failure_reason",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        columns = ", ".join(f"{key} = ?" for key in updates)
        params = list(updates.values()) + [account_id]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"UPDATE account_health SET {columns} WHERE account_id = ?", params)
            conn.commit()

    def list_accounts_with_health(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    a.id,
                    a.email,
                    a.password_encrypted,
                    a.phone,
                    a.openai_token,
                    a.refresh_token,
                    a.token_expires_at,
                    a.token_last_refreshed_at,
                    a.token_status,
                    a.token_refresh_error,
                    a.token_refresh_attempts,
                    a.plan,
                    a.status,
                    a.created_at,
                    a.updated_at,
                    h.runtime_status,
                    h.consecutive_failures,
                    h.total_failures,
                    h.cooldown_until,
                    h.last_check_at,
                    h.last_success_at,
                    h.last_failure_at,
                    h.last_failure_reason,
                    h.updated_at AS health_updated_at
                FROM accounts a
                LEFT JOIN account_health h ON h.account_id = a.id
                ORDER BY a.id DESC
                """
            ).fetchall()
        merged: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["password"] = self._decrypt(item.pop("password_encrypted"))
            account_id = int(item["id"])
            if item.get("runtime_status") is None:
                self.ensure_health_record(account_id)
                health = self.get_health(account_id) or {}
                for key, value in health.items():
                    item[key] = value
                item["health_updated_at"] = health.get("updated_at")
            merged.append(item)
        return merged

    def _encrypt(self, text: str) -> str:
        return encrypt_text(text, self.encryption_key)

    def _decrypt(self, encrypted: str) -> str:
        return decrypt_text(encrypted, self.encryption_key)
