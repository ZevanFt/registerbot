#!/usr/bin/env python3
"""Batch register accounts through /api/pipeline/register.

Usage:
  python scripts/register_batch.py --target 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Config:
    base_url: str
    username: str
    password: str
    target: int
    delay_seconds: float
    request_timeout: float
    max_failures: int


def _http_json(
    url: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 300.0,
) -> tuple[int, Any]:
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    data: bytes | None = None
    if body is not None:
        req_headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url=url, method=method, data=data, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"raw": raw}
            return int(resp.status), payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return int(exc.code), payload
    except urllib.error.URLError as exc:
        return 599, {"error": f"url_error: {exc}"}
    except TimeoutError:
        return 598, {"error": f"timeout after {timeout}s"}


def login(cfg: Config) -> str:
    status, payload = _http_json(
        f"{cfg.base_url}/api/auth/login",
        method="POST",
        body={"username": cfg.username, "password": cfg.password},
        timeout=cfg.request_timeout,
    )
    if status != 200 or not isinstance(payload, dict) or "token" not in payload:
        raise RuntimeError(f"login failed: status={status}, payload={payload}")
    return str(payload["token"])


def get_accounts_count(cfg: Config, token: str) -> int:
    status, payload = _http_json(
        f"{cfg.base_url}/api/accounts",
        headers={"Authorization": f"Bearer {token}"},
        timeout=cfg.request_timeout,
    )
    if status != 200 or not isinstance(payload, list):
        raise RuntimeError(f"list accounts failed: status={status}, payload={payload}")
    return len(payload)


def run_once(cfg: Config, token: str) -> tuple[bool, dict[str, Any]]:
    status, payload = _http_json(
        f"{cfg.base_url}/api/pipeline/register",
        method="POST",
        body={"email": None, "password": None},
        headers={"Authorization": f"Bearer {token}"},
        timeout=cfg.request_timeout,
    )
    if status == 200 and isinstance(payload, dict) and payload.get("success") is True:
        return True, payload
    return False, {"http_status": status, "response": payload}


def append_log(log_path: Path, line: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="Batch register accounts")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--username", default=os.environ.get("REGISTER_BOT_ADMIN_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("REGISTER_BOT_ADMIN_PASSWORD", ""))
    parser.add_argument("--target", type=int, default=10)
    parser.add_argument("--delay-seconds", type=float, default=3.0)
    parser.add_argument("--request-timeout", type=float, default=600.0)
    parser.add_argument("--max-failures", type=int, default=8)
    args = parser.parse_args()
    if args.target <= 0:
        parser.error("--target must be > 0")
    if not str(args.username).strip():
        parser.error("--username is required (or set REGISTER_BOT_ADMIN_USERNAME)")
    if not str(args.password).strip():
        parser.error("--password is required (or set REGISTER_BOT_ADMIN_PASSWORD)")
    return Config(
        base_url=str(args.base_url).rstrip("/"),
        username=str(args.username),
        password=str(args.password),
        target=int(args.target),
        delay_seconds=float(args.delay_seconds),
        request_timeout=float(args.request_timeout),
        max_failures=int(args.max_failures),
    )


def main() -> int:
    cfg = parse_args()
    started = time.strftime("%Y%m%d-%H%M%S")
    log_path = Path(".run") / f"register-batch-{started}.log"
    print(f"[INFO] log file: {log_path}")

    try:
        token = login(cfg)
    except Exception as exc:  # noqa: BLE001
        print(f"[FATAL] login failed: {exc}")
        return 1

    baseline = get_accounts_count(cfg, token)
    target_total = baseline + cfg.target
    print(f"[INFO] baseline_accounts={baseline}, target_new={cfg.target}, target_total={target_total}")
    append_log(log_path, json.dumps({"event": "start", "baseline": baseline, "target_total": target_total}, ensure_ascii=False))

    success_count = 0
    failure_count = 0
    attempt = 0
    while success_count < cfg.target:
        attempt += 1
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{ts}] attempt={attempt} success={success_count}/{cfg.target} failures={failure_count}")
        ok, result = run_once(cfg, token)
        if ok:
            success_count += 1
            email = str(result.get("email", ""))
            duration = result.get("total_duration")
            print(f"[OK] registered email={email} duration={duration}")
            append_log(
                log_path,
                json.dumps(
                    {"event": "success", "attempt": attempt, "success_count": success_count, "email": email, "result": result},
                    ensure_ascii=False,
                ),
            )
        else:
            failure_count += 1
            print(f"[FAIL] result={result}")
            append_log(
                log_path,
                json.dumps(
                    {"event": "failure", "attempt": attempt, "failure_count": failure_count, "detail": result},
                    ensure_ascii=False,
                ),
            )
            if failure_count >= cfg.max_failures:
                print(f"[STOP] failure_count reached max_failures={cfg.max_failures}")
                break

        if success_count < cfg.target:
            time.sleep(cfg.delay_seconds)

    current_total = get_accounts_count(cfg, token)
    print("\n[SUMMARY]")
    print(f"  success_count={success_count}")
    print(f"  failure_count={failure_count}")
    print(f"  accounts_total_now={current_total}")
    print(f"  log_file={log_path}")
    append_log(
        log_path,
        json.dumps(
            {
                "event": "summary",
                "success_count": success_count,
                "failure_count": failure_count,
                "accounts_total_now": current_total,
            },
            ensure_ascii=False,
        ),
    )
    return 0 if success_count >= cfg.target else 2


if __name__ == "__main__":
    sys.exit(main())
