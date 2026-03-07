#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
CHAT2API_DIR="${CHAT2API_DIR:-/home/talent/projects/chat2api}"
RUN_DIR="${ROOT_DIR}/.run"
LOG_DIR="${ROOT_DIR}/.run/logs"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
CHAT2API_HOST="${CHAT2API_HOST:-127.0.0.1}"
CHAT2API_PORT="${CHAT2API_PORT:-5005}"

mkdir -p "${RUN_DIR}" "${LOG_DIR}"

backend_pid_file="${RUN_DIR}/backend.pid"
frontend_pid_file="${RUN_DIR}/frontend.pid"
chat2api_pid_file="${RUN_DIR}/chat2api.pid"

backend_log="${LOG_DIR}/backend.log"
frontend_log="${LOG_DIR}/frontend.log"
chat2api_log="${LOG_DIR}/chat2api.log"

is_pid_running() {
  local pid="$1"
  kill -0 "${pid}" >/dev/null 2>&1
}

read_pid() {
  local pid_file="$1"
  if [[ -f "${pid_file}" ]]; then
    cat "${pid_file}"
  fi
}

is_service_running() {
  local pid_file="$1"
  local pid
  pid="$(read_pid "${pid_file}" || true)"
  [[ -n "${pid}" ]] && is_pid_running "${pid}"
}

start_chat2api() {
  if [[ ! -d "${CHAT2API_DIR}" ]]; then
    echo "[chat2api] skipped: dir not found: ${CHAT2API_DIR}"
    return 0
  fi
  if is_service_running "${chat2api_pid_file}"; then
    echo "[chat2api] already running (pid=$(read_pid "${chat2api_pid_file}"))"
    return 0
  fi
  echo "[chat2api] starting..."
  local py_cmd="python3"
  if [[ -x "${CHAT2API_DIR}/.venv/bin/python" ]]; then
    py_cmd="${CHAT2API_DIR}/.venv/bin/python"
  fi
  (
    cd "${CHAT2API_DIR}"
    nohup "${py_cmd}" app.py >"${chat2api_log}" 2>&1 &
    echo $! >"${chat2api_pid_file}"
  )
  sleep 1
  echo "[chat2api] pid=$(read_pid "${chat2api_pid_file}")"
}

start_backend() {
  if is_service_running "${backend_pid_file}"; then
    echo "[backend] already running (pid=$(read_pid "${backend_pid_file}"))"
    return 0
  fi
  echo "[backend] starting on ${BACKEND_HOST}:${BACKEND_PORT} ..."
  (
    cd "${BACKEND_DIR}"
    nohup .venv/bin/uvicorn app:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" >"${backend_log}" 2>&1 &
    echo $! >"${backend_pid_file}"
  )
  sleep 1
  echo "[backend] pid=$(read_pid "${backend_pid_file}")"
}

start_frontend() {
  if is_service_running "${frontend_pid_file}"; then
    echo "[frontend] already running (pid=$(read_pid "${frontend_pid_file}"))"
    return 0
  fi
  echo "[frontend] starting on ${FRONTEND_HOST}:${FRONTEND_PORT} ..."
  (
    cd "${FRONTEND_DIR}"
    nohup npm run dev -- --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}" --strictPort >"${frontend_log}" 2>&1 &
    echo $! >"${frontend_pid_file}"
  )
  sleep 1
  if ! is_service_running "${frontend_pid_file}"; then
    echo "[frontend] failed to start (see ${frontend_log})"
    return 1
  fi
  echo "[frontend] pid=$(read_pid "${frontend_pid_file}")"
}

stop_one() {
  local name="$1"
  local pid_file="$2"
  local pid
  pid="$(read_pid "${pid_file}" || true)"
  if [[ -z "${pid}" ]]; then
    echo "[${name}] not running"
    return 0
  fi
  if is_pid_running "${pid}"; then
    kill "${pid}" >/dev/null 2>&1 || true
    sleep 0.5
    if is_pid_running "${pid}"; then
      kill -9 "${pid}" >/dev/null 2>&1 || true
    fi
    echo "[${name}] stopped (pid=${pid})"
  else
    echo "[${name}] stale pid file removed (pid=${pid})"
  fi
  rm -f "${pid_file}"
}

check_http() {
  local name="$1"
  local url="$2"
  if curl -fsS -m 3 "${url}" >/dev/null; then
    echo "[check] ${name}: OK (${url})"
  else
    echo "[check] ${name}: FAIL (${url})"
  fi
}

check_http_reachable() {
  local name="$1"
  local url="$2"
  local code
  code="$(curl -sS -m 3 -o /dev/null -w "%{http_code}" "${url}" || true)"
  if [[ -n "${code}" && "${code}" != "000" ]]; then
    echo "[check] ${name}: OK (${url}, http=${code})"
  else
    echo "[check] ${name}: FAIL (${url})"
  fi
}

get_first_api_key() {
  python3 - "$ROOT_DIR" <<'PY'
import sqlite3, sys
from pathlib import Path
root = Path(sys.argv[1])
db = root / "backend" / "data" / "tokens.db"
if not db.exists():
    print("")
    raise SystemExit(0)
conn = sqlite3.connect(db)
try:
    row = conn.execute("SELECT key FROM tokens WHERE is_active=1 ORDER BY id DESC LIMIT 1").fetchone()
    print(row[0] if row else "")
finally:
    conn.close()
PY
}

check_chat_api() {
  local api_key
  api_key="$(get_first_api_key)"
  if [[ -z "${api_key}" ]]; then
    echo "[check] chat: SKIP (no active api key in backend/data/tokens.db)"
    return 0
  fi

  local models_url="http://${BACKEND_HOST}:${BACKEND_PORT}/v1/models"
  if curl -fsS -m 8 "${models_url}" -H "Authorization: Bearer ${api_key}" >/dev/null; then
    echo "[check] /v1/models: OK"
  else
    echo "[check] /v1/models: FAIL"
  fi

  local chat_payload
  chat_payload='{"model":"gpt-4o-mini","messages":[{"role":"user","content":"ping"}]}'
  local chat_url="http://${BACKEND_HOST}:${BACKEND_PORT}/v1/chat/completions"
  if curl -fsS -m 20 "${chat_url}" \
      -H "Authorization: Bearer ${api_key}" \
      -H "Content-Type: application/json" \
      -d "${chat_payload}" >/dev/null; then
    echo "[check] /v1/chat/completions: OK"
  else
    echo "[check] /v1/chat/completions: FAIL"
  fi
}

status() {
  local name pid_file addr pid
  for pair in \
    "chat2api ${chat2api_pid_file} ${CHAT2API_HOST}:${CHAT2API_PORT}" \
    "backend ${backend_pid_file} ${BACKEND_HOST}:${BACKEND_PORT}" \
    "frontend ${frontend_pid_file} ${FRONTEND_HOST}:${FRONTEND_PORT}"
  do
    # shellcheck disable=SC2086
    set -- $pair
    name="$1"; pid_file="$2"; addr="$3"
    pid="$(read_pid "${pid_file}" || true)"
    if [[ -n "${pid}" ]] && is_pid_running "${pid}"; then
      echo "[status] ${name}: RUNNING pid=${pid} addr=${addr}"
    else
      echo "[status] ${name}: STOPPED addr=${addr}"
    fi
  done
  check_http "backend-docs" "http://${BACKEND_HOST}:${BACKEND_PORT}/docs"
  check_http "frontend" "http://${FRONTEND_HOST}:${FRONTEND_PORT}"
  check_http_reachable "chat2api" "http://${CHAT2API_HOST}:${CHAT2API_PORT}"
}

up() {
  start_chat2api
  start_backend
  start_frontend
  echo
  status
}

down() {
  stop_one "frontend" "${frontend_pid_file}"
  stop_one "backend" "${backend_pid_file}"
  stop_one "chat2api" "${chat2api_pid_file}"
}

check() {
  status
  check_chat_api
}

usage() {
  cat <<EOF
Usage: $(basename "$0") <up|down|status|check|init-admin>

Commands:
  up      Start chat2api/backend/frontend in background
  down    Stop all started processes
  status  Show process + port status
  check   Run status and basic API/chat checks
  init-admin  Initialize admin user interactively (backend/config/settings.yaml + users table)
EOF
}

cmd="${1:-status}"
case "${cmd}" in
  up) up ;;
  down) down ;;
  status) status ;;
  check) check ;;
  init-admin)
    shift
    py_cmd="python3"
    if [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
      py_cmd="${BACKEND_DIR}/.venv/bin/python"
    fi
    "${py_cmd}" "${ROOT_DIR}/scripts/init_admin.py" "$@"
    ;;
  *) usage; exit 1 ;;
esac
