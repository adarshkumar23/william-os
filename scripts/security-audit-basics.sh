#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

require_header() {
  local headers="$1"
  local key="$2"
  if ! grep -qi "^${key}:" <<<"$headers"; then
    echo "[FAIL] Missing header: ${key}" >&2
    return 1
  fi
  echo "[PASS] Header present: ${key}"
}

echo "Running security baseline checks against ${BASE_URL}"

health_headers="$(curl -sS -D - -o /dev/null "${BASE_URL}/health")"
require_header "$health_headers" "x-content-type-options"
require_header "$health_headers" "x-frame-options"
require_header "$health_headers" "referrer-policy"
require_header "$health_headers" "content-security-policy"

auth_status="$(curl -sS -o /dev/null -w "%{http_code}" "${BASE_URL}/api/v1/auth/me")"
if [[ "$auth_status" != "422" && "$auth_status" != "401" ]]; then
  echo "[FAIL] /api/v1/auth/me unexpectedly returned ${auth_status}" >&2
  exit 1
fi
echo "[PASS] /api/v1/auth/me requires authentication (status ${auth_status})"

echo "Security baseline checks completed successfully."
