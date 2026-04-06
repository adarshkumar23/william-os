#!/bin/bash
set -euo pipefail
echo "=========================================="
echo "  WILLIAM OS — Setting up Codespace..."
echo "=========================================="

cd /workspace

# ── 1. Create .env from template if missing ──────────────────────
if [ ! -f .env ]; then
  cp .env.example .env

  # Generate secure secrets automatically
  JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
  ENC_SALT=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

  # Update .env with Codespace-specific values
  sed -i "s|JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${JWT_SECRET}|" .env
  sed -i "s|ENCRYPTION_MASTER_SALT=.*|ENCRYPTION_MASTER_SALT=${ENC_SALT}|" .env
  sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://william:william@postgres:5432/williamos|" .env
  sed -i "s|REDIS_URL=.*|REDIS_URL=redis://redis:6379/0|" .env

  echo "✅ .env created with auto-generated secrets"
else
  echo "ℹ️  .env already exists, skipping"
fi

# ── 2. Install Python dependencies ──────────────────────────────
echo "📦 Installing Python dependencies..."
cd /workspace/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e ".[dev]" -q
echo "✅ Python dependencies installed"

# ── 3. Wait for Postgres to be ready ────────────────────────────
echo "⏳ Waiting for PostgreSQL..."
for i in {1..30}; do
  if pg_isready -h postgres -U william -d williamos -q 2>/dev/null; then
    echo "✅ PostgreSQL is ready"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "⚠️  PostgreSQL not ready after 30s — will retry on start"
  fi
  sleep 1
done

# ── 4. Initialize database schemas ──────────────────────────────
echo "🗄️  Creating database schemas..."
PGPASSWORD=william psql -h postgres -U william -d williamos -f /workspace/scripts/init-schemas.sql -q 2>/dev/null || echo "ℹ️  Schemas may already exist"
echo "✅ Database schemas ready"

# ── 5. Install pre-commit hooks (optional) ──────────────────────
cd /workspace
if command -v git &>/dev/null; then
  cat > .git/hooks/pre-commit << 'HOOK'
#!/bin/bash
cd backend && source .venv/bin/activate 2>/dev/null
ruff check . --fix --quiet
ruff format . --quiet
HOOK
  chmod +x .git/hooks/pre-commit
  echo "✅ Pre-commit hook installed (auto-lint + format)"
fi

echo ""
echo "=========================================="
echo "  ✅ WILLIAM OS Codespace ready!"
echo ""
echo "  Run:  cd backend && source .venv/bin/activate"
echo "        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "  API docs: Open port 8000 in browser"
echo "=========================================="
