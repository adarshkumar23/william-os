#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-http://localhost:8000}"
USERS="${2:-25}"
SPAWN_RATE="${3:-5}"
DURATION="${4:-2m}"

echo "Running Locust smoke test"
echo "  host=${HOST} users=${USERS} spawn_rate=${SPAWN_RATE} duration=${DURATION}"

cd "$(dirname "$0")/../backend"
locust \
  -f tests/load/locustfile.py \
  --host "${HOST}" \
  --headless \
  -u "${USERS}" \
  -r "${SPAWN_RATE}" \
  -t "${DURATION}"
