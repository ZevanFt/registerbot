#!/usr/bin/env python3
"""Interactive bootstrap for admin user and auth settings."""

from __future__ import annotations

import argparse
import getpass
import secrets
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.storage.user_store import UserStore  # noqa: E402
from src.utils.passwords import hash_password  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize admin account for deployment")
    parser.add_argument(
        "--config",
        default=str(BACKEND_DIR / "config" / "settings.yaml"),
        help="Path to backend settings.yaml",
    )
    parser.add_argument("--username", default=None, help="Admin username")
    parser.add_argument("--password", default=None, help="Admin password")
    parser.add_argument("--email", default=None, help="Admin email (optional)")
    parser.add_argument("--jwt-secret", dest="jwt_secret", default=None, help="Admin JWT secret")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Fail if required arguments are missing instead of prompting",
    )
    return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"invalid yaml mapping: {path}")
    return payload


def save_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle, allow_unicode=True, default_flow_style=False, sort_keys=False)


def ask_text(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{suffix}: ").strip()
        if value:
            return value
        if default:
            return default
        print(f"{label} 不能为空。")


def ask_optional(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    if value:
        return value
    return default or ""


def ask_password(default_given: bool) -> str:
    if default_given:
        keep = input("是否保留当前密码? [y/N]: ").strip().lower()
        if keep == "y":
            return ""

    while True:
        first = getpass.getpass("管理员密码: ").strip()
        second = getpass.getpass("确认管理员密码: ").strip()
        if first != second:
            print("两次输入不一致，请重试。")
            continue
        if len(first) < 8:
            print("密码长度至少 8 位。")
            continue
        return first


def resolve_db_path(config_payload: dict[str, Any], config_path: Path) -> Path:
    storage = config_payload.get("storage")
    if not isinstance(storage, dict):
        storage = {}
    raw = str(storage.get("db_path") or "data/accounts.db")
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (config_path.parent.parent / candidate).resolve()


def upsert_admin_user(store: UserStore, username: str, password: str, email: str | None) -> str:
    now = datetime.now(timezone.utc).isoformat()
    existing = store.find_by_username(username)
    clean_email = email.strip() if isinstance(email, str) and email.strip() else None

    if existing is None:
        store.create_user(
            username=username,
            password=password,
            permission="admin",
            email=clean_email,
            is_active=True,
        )
        return "created"

    user_id = int(existing["id"])
    update_columns: list[str] = ["permission = ?", "is_active = ?", "updated_at = ?"]
    update_values: list[Any] = ["admin", 1, now]
    if clean_email is not None:
        update_columns.append("email = ?")
        update_values.append(clean_email)
    if password:
        update_columns.append("password_hash = ?")
        update_values.append(hash_password(password))
    update_values.append(user_id)

    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            f"UPDATE users SET {', '.join(update_columns)} WHERE id = ?",
            update_values,
        )
        conn.commit()
    return "updated"


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    payload = load_yaml(config_path)
    admin_cfg = payload.get("admin")
    if not isinstance(admin_cfg, dict):
        admin_cfg = {}

    default_username = str(admin_cfg.get("username") or "admin")
    current_password = str(admin_cfg.get("password") or "")
    current_jwt_secret = str(admin_cfg.get("jwt_secret") or "")
    auto_jwt_secret = current_jwt_secret if current_jwt_secret and current_jwt_secret != "change-me-in-production" else secrets.token_hex(32)

    if args.non_interactive:
        if not args.username or not args.password:
            raise SystemExit("--non-interactive requires --username and --password")
        username = args.username.strip()
        password = args.password.strip()
        email = (args.email or "").strip()
        jwt_secret = (args.jwt_secret or auto_jwt_secret).strip()
    else:
        print("=== 管理员初始化 ===")
        username = ask_text("管理员用户名", default=default_username)
        password = args.password.strip() if args.password else ask_password(default_given=bool(current_password))
        email = args.email.strip() if args.email is not None else ask_optional("管理员邮箱(可选)")
        jwt_secret = (args.jwt_secret or "").strip()
        if not jwt_secret:
            jwt_secret = ask_optional("JWT Secret (留空自动生成)", default=auto_jwt_secret) or auto_jwt_secret

    if not password:
        password = current_password
    if not password:
        raise SystemExit("管理员密码为空，请重新执行并输入密码。")
    if len(password) < 8:
        raise SystemExit("管理员密码长度至少 8 位。")
    if not jwt_secret:
        raise SystemExit("JWT Secret 不能为空。")

    admin_cfg["username"] = username
    admin_cfg["password"] = password
    admin_cfg["jwt_secret"] = jwt_secret
    admin_cfg["jwt_expire_hours"] = int(admin_cfg.get("jwt_expire_hours") or 24)
    payload["admin"] = admin_cfg
    save_yaml(config_path, payload)

    db_path = resolve_db_path(payload, config_path)
    store = UserStore(str(db_path))
    action = upsert_admin_user(store, username=username, password=password, email=email or None)

    print("")
    print("初始化完成:")
    print(f"- 配置文件: {config_path}")
    print(f"- 用户库: {db_path}")
    print(f"- 管理员: {username} ({action})")
    print("- 可登录地址: http://localhost:5173/#/login")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
