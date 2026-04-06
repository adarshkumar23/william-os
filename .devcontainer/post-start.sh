#!/bin/bash
set -euo pipefail

echo "🚀 WILLIAM OS — Starting services..."

# Wait for services
for i in {1..15}; do
  if pg_isready -h postgres -U william -d williamos -q 2>/dev/null; then
    break
  fi
  sleep 1
done

echo "✅ PostgreSQL: ready"
redis-cli -h redis ping -q 2>/dev/null && echo "✅ Redis: ready" || echo "⏳ Redis: starting..."

echo ""
echo "  To start the backend:"
echo "  cd backend && source .venv/bin/activate"
echo "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
