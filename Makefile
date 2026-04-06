.PHONY: help dev up down test lint migrate seed clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Development ──────────────────────────────────────────────────

up: ## Start all services (Docker Compose)
	docker compose up -d
	@echo "✅ WILLIAM OS running at http://localhost:8000"
	@echo "📊 Grafana at http://localhost:3001 (admin/william)"
	@echo "📈 Prometheus at http://localhost:9090"

down: ## Stop all services
	docker compose down

dev: ## Run backend in dev mode (hot reload)
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

logs: ## Tail backend logs
	docker compose logs -f backend

# ── Database ─────────────────────────────────────────────────────

migrate: ## Run Alembic migrations
	cd backend && alembic upgrade head

migrate-create: ## Create new migration (usage: make migrate-create MSG="add habits table")
	cd backend && alembic revision --autogenerate -m "$(MSG)"

db-reset: ## Drop and recreate database
	docker compose exec postgres psql -U william -d williamos -c "DROP SCHEMA IF EXISTS auth, scheduler, audit, habits, journal, medicine, email_intel, fitness, voice, study, trading, sleep, decisions, messaging CASCADE;"
	docker compose exec postgres psql -U william -d williamos -f /docker-entrypoint-initdb.d/01-schemas.sql
	cd backend && alembic upgrade head

# ── Testing ──────────────────────────────────────────────────────

test: ## Run all tests
	cd backend && pytest tests/ -v --cov=app --cov-report=term-missing

test-unit: ## Run unit tests only
	cd backend && pytest tests/unit/ -v

test-load: ## Run load tests (Locust)
	cd backend && locust -f tests/load/locustfile.py --host=http://localhost:8000

test-load-100: ## Headless load test: 100 users, 10 min
	cd backend && locust -f tests/load/locustfile.py --host=http://localhost:8000 --headless -u 100 -r 10 -t 10m

test-load-smoke: ## Quick headless load smoke test
	bash scripts/performance-smoke.sh http://localhost:8000 25 5 2m

audit-security: ## Run basic security audit checks
	bash scripts/security-audit-basics.sh http://localhost:8000

# ── Code Quality ─────────────────────────────────────────────────

lint: ## Run linter
	cd backend && ruff check . && ruff format --check .

format: ## Auto-format code
	cd backend && ruff format . && ruff check --fix .

typecheck: ## Run type checker
	cd backend && mypy app/ --ignore-missing-imports

# ── Utilities ────────────────────────────────────────────────────

clean: ## Remove build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf backend/.pytest_cache backend/htmlcov backend/.coverage

shell: ## Open Python shell with app context
	cd backend && python -c "import asyncio; from app.main import app; print('WILLIAM OS Shell Ready')"
