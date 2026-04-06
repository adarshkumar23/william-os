# WILLIAM OS — Architecture & System Design

## Vision
An autonomous daily-life orchestration system that adapts to real-time context,
learns user patterns, and operates as a personal AI operating system across
voice, mobile, web, and messaging interfaces.

## Architecture Style: Event-Driven Modular Monolith
We start as a **modular monolith** with strict module boundaries, an internal
event bus, and a shared PostgreSQL database. Each module owns its own schema
namespace. When a module needs to scale independently (e.g., voice processing),
we extract it into a microservice behind the same event contract.

**Why not microservices from day 1?**
- Solo developer + small team = operational overhead kills velocity
- Modular monolith lets us refactor boundaries cheaply
- PostgreSQL schemas give us logical isolation without network hops

---

## Module Map

| # | Module                  | Schema Namespace   | Priority | Sprint |
|---|-------------------------|--------------------|----------|--------|
| 1 | Core Platform           | `core`             | P0       | 1      |
| 2 | Auth & Multi-User       | `auth`             | P0       | 1      |
| 3 | Dynamic Scheduler       | `scheduler`        | P0       | 1-2    |
| 4 | Email Intelligence      | `email_intel`      | P1       | 2      |
| 5 | Fitness Intelligence    | `fitness`          | P1       | 2-3    |
| 6 | Voice Interface         | `voice`            | P1       | 3      |
| 7 | Study Mentor (IAS)      | `study`            | P1       | 3      |
| 8 | Trading Dashboard       | `trading`          | P2       | 3-4    |
| 9 | Journal Vault           | `journal`          | P1       | 2      |
| 10| Habit Tracker           | `habits`           | P1       | 2      |
| 11| Sleep Optimizer         | `sleep`            | P2       | 3      |
| 12| Decision Assistant      | `decisions`        | P2       | 4      |
| 13| Medicine Reminders      | `medicine`         | P1       | 2      |
| 14| Messaging (TG/WA)      | `messaging`        | P1       | 3      |
| 15| Audit & Analytics       | `audit`            | P0       | 1      |

---

## Tech Stack Decisions

### Backend: Python 3.12 + FastAPI
**Why:** Async-native, best AI/ML library ecosystem, type-safe with Pydantic,
auto-generated OpenAPI docs, first-class WebSocket support for real-time voice.

### Database: PostgreSQL 16 + pgcrypto + pg_cron
**Why:** JSONB for flexible schema evolution, Row-Level Security for multi-user,
pgcrypto for journal encryption at rest, pg_cron for midnight schedule regen.

### Task Queue: Celery + Redis
**Why:** Midnight schedule generation, email summarization, fitness sync — all
async background jobs. Redis doubles as cache layer.

### Frontend: React 18 (Web) + React Native (Mobile)
**Why:** Shared component logic, massive ecosystem, strong TypeScript support.

### AI APIs:
- **Gemini 2.0 Flash** → Schedule generation + rescheduling (fast, cheap)
- **OpenRouter** → Health analysis, decision support (model flexibility)
- **Whisper** → Voice transcription (local or API)
- **Alexa Skills Kit** → Voice-first home interface

### Infrastructure:
- **Oracle Cloud** → Always-free tier ARM instances (4 OCPU, 24GB RAM)
- **Google Cloud** → $300 credits for Gemini API + Cloud Run overflow
- **Cloudflare** → CDN, DNS, DDoS protection (free tier)

---

## Data Flow: Daily Lifecycle

```
┌──────────────────────────────────────────────────────┐
│                    MIDNIGHT CYCLE                     │
│                                                       │
│  pg_cron trigger → Celery task → Gemini API           │
│  Inputs: calendar, habits, sleep data, priorities     │
│  Output: optimized daily schedule → scheduler.plans   │
│  Notify: push notification "Your day is ready"        │
└──────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│                  PRE-WAKE CYCLE                       │
│                                                       │
│  30 min before alarm → email summarization            │
│  Gmail/Outlook IMAP → OpenRouter summary              │
│  Weather + commute → schedule adjustments             │
│  Output: morning briefing notification                │
└──────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│                   ACTIVE DAY                          │
│                                                       │
│  Real-time rescheduling via voice/chat                │
│  Habit check-ins, medicine reminders                  │
│  Energy forecasting based on activity + sleep         │
│  Procrastination detection (missed check-ins)         │
└──────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│                   NIGHT CYCLE                         │
│                                                       │
│  Daily journal prompt                                 │
│  Sleep optimization recommendation                   │
│  Day score calculation                                │
│  Data sync across devices                             │
│  Encrypted backup                                     │
└──────────────────────────────────────────────────────┘
```

---

## Security Architecture

### Authentication
- JWT access tokens (15 min) + refresh tokens (7 days)
- Device fingerprinting for multi-device
- Optional TOTP 2FA

### Encryption
- Journal entries: AES-256-GCM, per-user key derived from passphrase (PBKDF2)
- Database: TLS in transit, pgcrypto at rest for sensitive columns
- API keys: encrypted in DB, decrypted only in memory

### Privacy
- All AI API calls strip PII before sending
- User can export ALL data as JSON (GDPR-style)
- User can delete account + all data with single action
- Audit log tracks every data access

---

## Directory Structure

```
william-os/
├── backend/
│   ├── alembic/              # DB migrations
│   ├── app/
│   │   ├── core/             # Config, security, deps
│   │   ├── modules/
│   │   │   ├── auth/
│   │   │   ├── scheduler/
│   │   │   ├── email_intel/
│   │   │   ├── fitness/
│   │   │   ├── voice/
│   │   │   ├── study/
│   │   │   ├── trading/
│   │   │   ├── journal/
│   │   │   ├── habits/
│   │   │   ├── sleep/
│   │   │   ├── decisions/
│   │   │   ├── medicine/
│   │   │   ├── messaging/
│   │   │   └── audit/
│   │   ├── shared/           # Event bus, base models, utils
│   │   └── main.py
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── web/                  # React web app
│   └── mobile/               # React Native app
├── infra/
│   ├── docker-compose.yml
│   ├── nginx/
│   ├── terraform/            # Oracle Cloud IaC
│   └── monitoring/           # Prometheus + Grafana
├── n8n/                      # N8N workflow exports
├── docs/
├── scripts/
├── .github/workflows/        # CI/CD
└── ARCHITECTURE.md
```

---

## API Design Conventions

- RESTful with consistent envelope: `{ "ok": bool, "data": T, "error": str }`
- Versioned: `/api/v1/...`
- Rate limited per user tier
- WebSocket at `/ws/v1/...` for real-time (voice, live schedule)
- All timestamps in UTC ISO-8601
- Pagination: cursor-based (not offset)

---

## Sprint Plan (4-6 Weeks)

### Sprint 1 (Week 1-2): Foundation + Core
- [x] Architecture document
- [ ] Project scaffolding + Docker Compose
- [ ] PostgreSQL schema + migrations
- [ ] Auth module (JWT + multi-user)
- [ ] Core event bus
- [ ] Audit trail module
- [ ] Dynamic Scheduler v1 (Gemini integration)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Basic React web shell

### Sprint 2 (Week 2-3): Daily Intelligence
- [ ] Email Intelligence (Gmail IMAP + summarization)
- [ ] Habit Tracker + procrastination detection
- [ ] Journal Vault (encrypted)
- [ ] Medicine/supplement reminders
- [ ] Morning briefing flow

### Sprint 3 (Week 3-4): Interfaces + Health
- [ ] Voice interface (Whisper + Alexa)
- [ ] Fitness intelligence (watch data sync)
- [ ] Study Mentor module
- [ ] Messaging integration (Telegram)
- [ ] React Native mobile shell

### Sprint 4 (Week 4-6): Polish + Ship
- [ ] Trading dashboard
- [ ] Sleep optimizer
- [ ] Decision assistant
- [ ] Load testing (Locust)
- [ ] Offline fallback mode
- [ ] Multi-device sync
- [ ] Data export
- [ ] Production deployment
- [ ] Documentation

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Gemini API rate limits | Schedule gen fails | Queue + retry + fallback to rule-based |
| Oracle free tier limits | Server crashes | Auto-scale to GCP Cloud Run |
| Scope creep | MVP delayed | Strict P0/P1/P2 prioritization |
| API key exposure | Security breach | Vault + env vars + rotation policy |
| Single developer bus factor | Project stalls | Clean docs + modular code = easy handoff |
