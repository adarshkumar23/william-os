# 🧠 WILLIAM OS — Personal AI Operating System

> An autonomous daily-life orchestration system that adapts to your real-time schedule, learns your patterns, and operates as your personal AI bodyguard, trainer, study mentor, health coach, and decision partner.

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your API keys (Gemini, OpenRouter, etc.)

# 2. Start everything
make up

# 3. Verify
curl http://localhost:8000/health
# → {"status": "ok", "version": "0.1.0", ...}

# 4. Open API docs
open http://localhost:8000/docs
```

## Architecture

**Event-Driven Modular Monolith** — strict module boundaries, internal async event bus, shared PostgreSQL with per-module schema namespaces.

```
┌─────────────────────────────────────────────────────────┐
│                    WILLIAM OS                            │
│                                                          │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌────────┐ │
│  │   Auth   │  │ Scheduler │  │  Habits  │  │ Audit  │ │
│  └────┬─────┘  └─────┬─────┘  └────┬─────┘  └───┬────┘ │
│       │              │              │             │      │
│  ─────┴──────────────┴──────────────┴─────────────┴───  │
│                    Event Bus                             │
│  ─────┬──────────────┬──────────────┬─────────────┬───  │
│       │              │              │             │      │
│  ┌────┴─────┐  ┌─────┴─────┐  ┌────┴─────┐  ┌───┴────┐ │
│  │ Journal  │  │  Medicine │  │  Fitness │  │ Voice  │ │
│  └──────────┘  └───────────┘  └──────────┘  └────────┘ │
│                                                          │
│  PostgreSQL │ Redis │ Celery │ Gemini AI │ OpenRouter    │
└─────────────────────────────────────────────────────────┘
```

## Modules

| Module | Status | Description |
|--------|--------|-------------|
| **Auth** | ✅ Built | JWT + multi-user + device tracking + family ecosystem |
| **Scheduler** | ✅ Built | Gemini-powered daily plan generation + rescheduling |
| **Audit** | ✅ Built | Immutable event-sourced audit trail |
| **Habits** | 🔧 Schema | Habit tracking + streak + procrastination detection |
| **Journal** | 🔧 Schema | AES-256-GCM encrypted private journal vault |
| **Medicine** | 🔧 Schema | User-configured supplement/medicine reminders |
| Fitness | 📋 Planned | Watch data sync + health AI analysis |
| Voice | 📋 Planned | Whisper + Alexa Skills Kit |
| Study | 📋 Planned | IAS exam mentor + spaced repetition |
| Trading | 📋 Planned | Market dashboard + alerts |
| Sleep | 📋 Planned | Sleep optimization + energy forecasting |
| Decisions | 📋 Planned | AI decision support framework |
| Messaging | 📋 Planned | Telegram + WhatsApp family messaging |

## Tech Stack

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy 2.0 (async)
- **Database:** PostgreSQL 16 + pgcrypto
- **Queue:** Celery + Redis
- **AI:** Gemini 2.0 Flash + OpenRouter + Whisper
- **Frontend:** React 18 (web) + React Native (mobile)
- **Infra:** Docker Compose → Oracle Cloud + Google Cloud
- **Monitoring:** Prometheus + Grafana
- **CI/CD:** GitHub Actions

## Development

```bash
make help          # Show all commands
make dev           # Run backend with hot reload
make test          # Run all tests
make lint          # Check code quality
make migrate       # Run database migrations
make db-reset      # Reset database
make test-load     # Run Locust load tests
```

## API Endpoints

All responses use envelope: `{ "ok": bool, "data": T, "error": str }`

### Auth
- `POST /api/v1/auth/register` — Create account
- `POST /api/v1/auth/login` — Login + get tokens
- `POST /api/v1/auth/refresh` — Refresh JWT tokens
- `GET  /api/v1/auth/me` — Get current user profile

### Scheduler
- `POST /api/v1/schedule/generate` — Generate daily plan (Gemini AI)
- `GET  /api/v1/schedule/today` — Get today's plan
- `GET  /api/v1/schedule/{date}` — Get plan by date
- `POST /api/v1/schedule/{date}/blocks` — Add manual block
- `PATCH /api/v1/schedule/blocks/{id}` — Update block
- `POST /api/v1/schedule/blocks/{id}/start` — Start a block
- `POST /api/v1/schedule/{date}/reschedule` — AI-powered reschedule

## Security

- JWT access (15 min) + refresh (7 days) with token rotation
- AES-256-GCM encryption for journal entries (per-user passphrase)
- Bcrypt password hashing (auto-tuned cost factor)
- Device fingerprinting for multi-device awareness
- All AI API calls strip PII before sending
- Full audit trail on every action

## License

AGPL-3.0 — Open source core, commercial SaaS license available.
