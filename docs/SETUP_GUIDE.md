# WILLIAM OS — Complete Installation & Setup Guide

> From zero to running in 15 minutes. Every step tested and verified.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [System Requirements](#2-system-requirements)
3. [Clone & Configure](#3-clone--configure)
4. [Environment Variables Setup](#4-environment-variables-setup)
5. [Option A: Docker Setup (Recommended)](#5-option-a-docker-setup-recommended)
6. [Option B: Manual Local Setup](#6-option-b-manual-local-setup)
7. [Verify Installation](#7-verify-installation)
8. [First Run Walkthrough](#8-first-run-walkthrough)
9. [API Keys Setup Guide](#9-api-keys-setup-guide)
10. [Production Deployment (Oracle Cloud)](#10-production-deployment-oracle-cloud)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Prerequisites

Install these before anything else:

### Required (All Platforms)

| Tool | Version | Purpose | Install |
|------|---------|---------|---------|
| **Git** | 2.40+ | Version control | `https://git-scm.com/downloads` |
| **Docker Desktop** | 4.25+ | Containers | `https://docker.com/products/docker-desktop` |
| **Docker Compose** | 2.20+ | Multi-container | Included with Docker Desktop |
| **Node.js** | 20 LTS | Frontend build | `https://nodejs.org` |
| **Python** | 3.11+ | Backend (if running locally) | `https://python.org` |

### Check Versions

```bash
git --version          # >= 2.40
docker --version       # >= 24.0
docker compose version # >= 2.20
node --version         # >= 20.0
python3 --version      # >= 3.11
```

---

## 2. System Requirements

### Development Machine

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 4 GB | 8 GB |
| Storage | 5 GB | 10 GB |
| CPU | 2 cores | 4 cores |
| OS | macOS 12+ / Ubuntu 22+ / Windows 11 (WSL2) | macOS or Linux |

### Windows Users: WSL2 Required

```powershell
# In PowerShell as Administrator
wsl --install -d Ubuntu-24.04
# Restart, then run all commands inside WSL2 terminal
```

---

## 3. Clone & Configure

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/william-os.git
cd william-os

# Create your environment file from template
cp .env.example .env
```

---

## 4. Environment Variables Setup

Open `.env` in your editor and configure each section:

```bash
nano .env   # or: code .env (VS Code)
```

### Minimum Required for First Boot

```env
# ── These work out of the box (Docker defaults) ─────────────
ENVIRONMENT=development
DEBUG=true
DATABASE_URL=postgresql+asyncpg://william:william@localhost:5432/williamos
REDIS_URL=redis://localhost:6379/0

# ── CHANGE THESE (security) ─────────────────────────────────
JWT_SECRET_KEY=generate-a-random-64-char-string-here
ENCRYPTION_MASTER_SALT=generate-another-random-string-here
```

### Generate Secure Keys

```bash
# Generate JWT secret (run this and paste into .env)
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# Generate encryption salt
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Optional API Keys (Add When Ready)

```env
# Gemini AI — for schedule generation (free tier: 15 RPM)
GEMINI_API_KEY=your-key-here

# OpenRouter — for health AI analysis
OPENROUTER_API_KEY=your-key-here

# Telegram Bot — for family messaging
TELEGRAM_BOT_TOKEN=your-bot-token
```

> **Note:** WILLIAM OS works without API keys! The scheduler falls back to a
> rule-based schedule generator. Add keys when you're ready.

---

## 5. Option A: Docker Setup (Recommended)

This is the fastest path. One command starts everything.

### Step 1: Start All Services

```bash
make up
# Or without Make:
docker compose up -d
```

This starts 6 containers:

| Container | Port | Purpose |
|-----------|------|---------|
| `william-postgres` | 5432 | PostgreSQL 16 database |
| `william-redis` | 6379 | Cache + task queue |
| `william-backend` | **8000** | FastAPI backend (your main API) |
| `william-celery` | — | Background task worker |
| `william-celery-beat` | — | Scheduled task runner |
| `william-prometheus` | 9090 | Metrics collection |
| `william-grafana` | 3001 | Monitoring dashboard |

### Step 2: Wait for Healthy Status

```bash
# Watch containers start (takes 30-60 seconds first time)
docker compose ps

# Wait for all services to be "healthy"
docker compose logs -f backend
# Look for: "william_os_ready"
```

### Step 3: Verify

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-04-06T..."
}
```

### Useful Docker Commands

```bash
make up          # Start everything
make down        # Stop everything
make logs        # Tail backend logs
make db-reset    # Reset database (caution: deletes data)

# Manual alternatives
docker compose up -d               # Start
docker compose down                # Stop
docker compose logs -f backend     # Logs
docker compose exec postgres psql -U william -d williamos  # DB shell
docker compose exec redis redis-cli                        # Redis shell
```

---

## 6. Option B: Manual Local Setup

For development without Docker (or if you prefer running services natively).

### Step 1: Install PostgreSQL

**macOS:**
```bash
brew install postgresql@16
brew services start postgresql@16
createuser william -P   # Set password: william
createdb williamos -O william
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql-16 postgresql-client-16
sudo -u postgres createuser william -P
sudo -u postgres createdb williamos -O william
```

**Windows (WSL2):**
```bash
sudo apt install postgresql
sudo service postgresql start
sudo -u postgres createuser william -P
sudo -u postgres createdb williamos -O william
```

### Step 2: Create Database Schemas

```bash
psql -U william -d williamos -f scripts/init-schemas.sql
```

### Step 3: Install Redis

**macOS:**
```bash
brew install redis
brew services start redis
```

**Ubuntu:**
```bash
sudo apt install redis-server
sudo systemctl start redis-server
```

### Step 4: Set Up Python Environment

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Step 5: Run Database Migrations

```bash
cd backend
alembic upgrade head
```

### Step 6: Start the Backend

```bash
# From backend/ directory, with venv activated
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 7: Start Celery Workers (Separate Terminal)

```bash
cd backend
source .venv/bin/activate

# Worker (processes tasks)
celery -A app.worker worker -l info -c 2

# Beat (schedules periodic tasks) — another terminal
celery -A app.worker beat -l info
```

---

## 7. Verify Installation

Run these checks in order:

### Health Check
```bash
curl http://localhost:8000/health
# → {"status": "ok", ...}
```

### API Documentation
Open in browser: **http://localhost:8000/docs**

You should see the interactive Swagger UI with all endpoints.

### Register Your First User
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@example.com",
    "username": "william",
    "password": "YourStrongPass1",
    "full_name": "Your Name",
    "timezone": "Asia/Kolkata"
  }'
```

### Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@example.com",
    "password": "YourStrongPass1",
    "device_name": "MacBook Pro",
    "device_type": "web"
  }'
```

Save the `access_token` from the response!

### Generate Your First Schedule
```bash
TOKEN="your-access-token-here"

curl -X POST http://localhost:8000/api/v1/schedule/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "target_date": "2026-04-07",
    "extra_context": {
      "priorities": ["Prepare IAS prelims notes", "Complete gym workout", "Review trading portfolio"]
    }
  }'
```

### Run Tests
```bash
make test
# Or: cd backend && pytest tests/ -v
```

---

## 8. First Run Walkthrough

After installation, here's your first day with WILLIAM OS:

### Morning Setup (5 minutes)

1. **Register** → creates your account with timezone and wake/sleep times
2. **Generate schedule** → Gemini AI builds your optimized day
3. **View today** → `GET /api/v1/schedule/today`
4. **Start a block** → `POST /api/v1/schedule/blocks/{id}/start`

### During the Day

5. **Complete blocks** → `PATCH /api/v1/schedule/blocks/{id}` with `{"status": "completed"}`
6. **Need to reschedule?** → `POST /api/v1/schedule/{date}/reschedule`
7. **Add an unplanned task** → `POST /api/v1/schedule/{date}/blocks`

### Evening

8. Check your audit trail at `/api/v1/audit/logs`
9. Tomorrow's schedule auto-generates at midnight!

---

## 9. API Keys Setup Guide

### Gemini API (Schedule Generation)

1. Go to **https://aistudio.google.com/apikey**
2. Click "Create API Key"
3. Select or create a Google Cloud project
4. Copy the key → paste into `.env` as `GEMINI_API_KEY`

> **Free tier:** 15 requests/minute, 1M tokens/day — more than enough.

### OpenRouter (Health AI)

1. Go to **https://openrouter.ai/keys**
2. Create an account and add credits ($5 minimum)
3. Create a new API key
4. Copy → paste into `.env` as `OPENROUTER_API_KEY`

### Telegram Bot (Family Messaging)

1. Open Telegram, search for **@BotFather**
2. Send `/newbot`
3. Choose a name: "William OS"
4. Choose a username: `your_william_os_bot`
5. Copy the token → paste into `.env` as `TELEGRAM_BOT_TOKEN`

### Gmail API (Email Intelligence)

1. Go to **https://console.cloud.google.com/apis/credentials**
2. Create OAuth 2.0 credentials (Web Application)
3. Add redirect URI: `http://localhost:8000/api/v1/email/callback`
4. Copy Client ID → `GMAIL_CLIENT_ID`
5. Copy Client Secret → `GMAIL_CLIENT_SECRET`

---

## 10. Production Deployment (Oracle Cloud)

### Oracle Cloud Free Tier Setup

1. **Create account** at `https://cloud.oracle.com`
2. **Provision ARM instance:**
   - Shape: `VM.Standard.A1.Flex` (4 OCPU, 24 GB RAM — FREE)
   - OS: Ubuntu 24.04
   - Boot volume: 100 GB

3. **SSH and install Docker:**
```bash
ssh -i ~/.ssh/oracle_key ubuntu@YOUR_IP

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Logout and re-login

# Install Docker Compose
sudo apt install docker-compose-plugin
```

4. **Clone and configure:**
```bash
git clone https://github.com/YOUR_USERNAME/william-os.git
cd william-os
cp .env.example .env
nano .env  # Set ENVIRONMENT=production, real keys, strong secrets
```

5. **Start production stack:**
```bash
docker compose -f docker-compose.yml up -d
```

6. **Set up Nginx reverse proxy:**
```bash
sudo apt install nginx certbot python3-certbot-nginx
# Configure Nginx to proxy to localhost:8000
# Get free SSL with: sudo certbot --nginx -d yourdomain.com
```

7. **Firewall:**
```bash
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
# Block direct access to 8000 from outside
```

### Google Cloud ($300 Credits)

Use for Gemini API calls and as overflow/failover:

1. Create project at `https://console.cloud.google.com`
2. Enable Gemini API
3. Create API key
4. $300 credits last 90 days — enough for development phase

---

## 11. Troubleshooting

### Docker Won't Start

```bash
# Check if Docker daemon is running
docker info

# macOS: Open Docker Desktop app
# Linux: sudo systemctl start docker
# Windows: Start Docker Desktop
```

### Port Already in Use

```bash
# Find what's using port 8000
lsof -i :8000
# Kill it
kill -9 <PID>

# Or change port in docker-compose.yml:
# ports: - "8001:8000"
```

### Database Connection Refused

```bash
# Check if Postgres is running
docker compose ps postgres
# Restart it
docker compose restart postgres

# Check logs
docker compose logs postgres
```

### "Permission denied" on Linux

```bash
# Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in
```

### Migrations Fail

```bash
# Reset and retry
make db-reset
cd backend && alembic upgrade head
```

### Celery Tasks Not Running

```bash
# Check worker logs
docker compose logs celery-worker

# Check beat logs
docker compose logs celery-beat

# Verify Redis connection
docker compose exec redis redis-cli ping
# → PONG
```

### Backend Crashes on Startup

```bash
# Check full logs
docker compose logs backend --tail=50

# Common issues:
# 1. Missing .env file → cp .env.example .env
# 2. Database not ready → wait for postgres healthy
# 3. Bad CORS_ORIGINS → check format: comma-separated URLs
```

### "Module not found" in Local Setup

```bash
# Make sure venv is activated
source .venv/bin/activate

# Reinstall in editable mode
pip install -e ".[dev]"
```

### How to Completely Reset

```bash
# Nuclear option: remove everything and start fresh
docker compose down -v   # -v removes volumes (DATABASE DELETED)
docker system prune -af  # Clean all images
make up                  # Fresh start
```

---

## Quick Reference Card

| Action | Command |
|--------|---------|
| Start everything | `make up` |
| Stop everything | `make down` |
| View logs | `make logs` |
| Run tests | `make test` |
| Lint code | `make lint` |
| API docs | `http://localhost:8000/docs` |
| Grafana | `http://localhost:3001` (admin/william) |
| Prometheus | `http://localhost:9090` |
| DB shell | `docker compose exec postgres psql -U william -d williamos` |
| Redis shell | `docker compose exec redis redis-cli` |

---

*Last updated: April 2026 | WILLIAM OS v0.1.0*
