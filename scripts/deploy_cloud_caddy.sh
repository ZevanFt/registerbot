#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${DOMAIN:-codex.talenting.vip}"
EMAIL="${EMAIL:-}"
FRONTEND_DIST="${FRONTEND_DIST:-/opt/register-bot/frontend/dist}"
BACKEND_UPSTREAM="${BACKEND_UPSTREAM:-127.0.0.1:8001}"
CADDYFILE_PATH="${CADDYFILE_PATH:-/etc/caddy/Caddyfile}"

usage() {
  cat <<EOF
Usage: bash $(basename "$0") [--domain codex.talenting.vip] [--email you@example.com]

Environment variables:
  DOMAIN            default: codex.talenting.vip
  EMAIL             default: (empty, Caddy global email omitted)
  FRONTEND_DIST     default: /opt/register-bot/frontend/dist
  BACKEND_UPSTREAM  default: 127.0.0.1:8001
  CADDYFILE_PATH    default: /etc/caddy/Caddyfile
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="${2:-}"; shift 2 ;;
    --email)
      EMAIL="${2:-}"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 1 ;;
  esac
done

if [[ ! -d "${FRONTEND_DIST}" ]]; then
  echo "frontend dist not found: ${FRONTEND_DIST}" >&2
  echo "请先在云端执行: cd /opt/register-bot/frontend && npm install && npm run build" >&2
  exit 1
fi

if ! command -v caddy >/dev/null 2>&1; then
  echo "caddy not found, installing..."
  sudo apt update
  sudo apt install -y caddy
fi

tmpfile="$(mktemp)"
{
  if [[ -n "${EMAIL}" ]]; then
    cat <<EOF
{
  email ${EMAIL}
}

EOF
  fi

  cat <<EOF
${DOMAIN} {
  encode gzip zstd

  root * ${FRONTEND_DIST}
  file_server

  @api path /api/*
  reverse_proxy @api ${BACKEND_UPSTREAM}

  @v1 path /v1/*
  reverse_proxy @v1 ${BACKEND_UPSTREAM}

  @ws path /ws/*
  reverse_proxy @ws ${BACKEND_UPSTREAM}

  try_files {path} /index.html
}
EOF
} > "${tmpfile}"

sudo mkdir -p "$(dirname "${CADDYFILE_PATH}")"
if [[ -f "${CADDYFILE_PATH}" ]]; then
  sudo cp "${CADDYFILE_PATH}" "${CADDYFILE_PATH}.bak.$(date +%Y%m%d%H%M%S)"
fi
sudo cp "${tmpfile}" "${CADDYFILE_PATH}"
rm -f "${tmpfile}"

sudo caddy validate --config "${CADDYFILE_PATH}"
sudo systemctl restart caddy
sudo systemctl status caddy --no-pager -l | head -n 20

echo
echo "Caddy deployed:"
echo "- domain:   ${DOMAIN}"
echo "- frontend: ${FRONTEND_DIST}"
echo "- backend:  ${BACKEND_UPSTREAM}"
echo "- caddyfile:${CADDYFILE_PATH}"
