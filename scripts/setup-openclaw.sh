#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENCLAW_HOME="${OPENCLAW_HOME:-/opt/openclaw}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ENV_FILE="${OPENCLAW_HOME}/.env"
SKILL_SOURCE="${ROOT_DIR}/openclaw-skill/william-os"
SKILL_TARGET="${OPENCLAW_HOME}/skills/william-os"

printf "[openclaw] root: %s\n" "$ROOT_DIR"
printf "[openclaw] home: %s\n" "$OPENCLAW_HOME"

mkdir -p "${OPENCLAW_HOME}/skills"
mkdir -p "${OPENCLAW_HOME}/logs"

if [[ ! -d "${OPENCLAW_HOME}/.venv" ]]; then
  "${PYTHON_BIN}" -m venv "${OPENCLAW_HOME}/.venv"
fi

# shellcheck disable=SC1091
source "${OPENCLAW_HOME}/.venv/bin/activate"
pip install --upgrade pip >/dev/null
pip install httpx >/dev/null

if [[ -f "${OPENCLAW_HOME}/requirements.txt" ]]; then
  pip install -r "${OPENCLAW_HOME}/requirements.txt"
fi

rm -rf "$SKILL_TARGET"
cp -R "$SKILL_SOURCE" "$SKILL_TARGET"

if [[ ! -f "$ENV_FILE" ]]; then
  cat > "$ENV_FILE" <<'EOF'
WILLIAM_API_BASE_URL=http://127.0.0.1:8000/api/v1
WILLIAM_GATEWAY_BEARER_TOKEN=
WILLIAM_GATEWAY_TIMEOUT_SECONDS=20
OPENCLAW_TELEGRAM_BOT_TOKEN=
OPENCLAW_WHATSAPP_TOKEN=
OPENCLAW_DISCORD_TOKEN=
EOF
  printf "[openclaw] created %s\n" "$ENV_FILE"
else
  printf "[openclaw] reusing existing %s\n" "$ENV_FILE"
fi

if [[ $EUID -eq 0 ]]; then
  install -m 0644 "${ROOT_DIR}/infra/systemd/openclaw.service" /etc/systemd/system/openclaw.service
  systemctl daemon-reload
  printf "[openclaw] installed systemd unit: openclaw.service\n"
  printf "[openclaw] run: systemctl enable --now openclaw.service\n"
else
  printf "[openclaw] tip: run as root to install systemd unit\n"
fi

printf "[openclaw] setup complete\n"
printf "[openclaw] next: edit %s and set WILLIAM_GATEWAY_BEARER_TOKEN\n" "$ENV_FILE"
