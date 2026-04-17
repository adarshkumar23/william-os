#!/bin/bash
# Deploy / update William OS on Oracle VM
# Run from /opt/william-os
# Usage: bash scripts/deploy.sh [--pull]
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

# ── Pull latest if requested ────────────────────────────────────
if [[ "${1:-}" == "--pull" ]]; then
  echo "==> Pulling latest from origin/main"
  git pull origin main
fi

# ── Validate .env ────────────────────────────────────────────────
if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example and fill values."
  exit 1
fi

source .env 2>/dev/null || true

if [ -z "${JWT_SECRET_KEY:-}" ]; then
  echo "ERROR: JWT_SECRET_KEY is not set in .env"
  exit 1
fi

if [ -z "${ENCRYPTION_MASTER_SALT:-}" ]; then
  echo "ERROR: ENCRYPTION_MASTER_SALT is not set in .env"
  exit 1
fi

# ── Build & start containers ─────────────────────────────────────
echo "==> Building and starting Docker services"
docker compose pull --quiet redis postgres 2>/dev/null || true
docker compose build --no-cache backend frontend
docker compose up -d

# ── Wait for postgres ────────────────────────────────────────────
echo "==> Waiting for PostgreSQL to be ready"
timeout 60 bash -c 'until docker compose exec -T postgres pg_isready -U william -d williamos; do sleep 2; done'

# ── Run migrations ───────────────────────────────────────────────
echo "==> Running Alembic migrations"
docker compose exec -T backend alembic upgrade head

# ── Show status ──────────────────────────────────────────────────
echo ""
docker compose ps
echo ""
echo "✅ William OS deployed."
echo "   Backend : http://$(curl -s ifconfig.me 2>/dev/null || echo '<vm-ip>'):8000"
echo "   Health  : http://$(curl -s ifconfig.me 2>/dev/null || echo '<vm-ip>'):8000/health"
