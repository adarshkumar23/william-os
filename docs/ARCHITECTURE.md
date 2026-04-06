# WILLIAM OS — Architecture Document
## Personal AI Operating System

**Version:** 1.0.0
**Author:** William OS Engineering
**Last Updated:** 2026-04-06
**Status:** Active Development — MVP Sprint

---

## 1. System Overview

WILLIAM OS is an autonomous daily-life orchestration system built as a modular,
event-driven platform. It adapts to real-time schedules, learns behavioral
patterns, and serves as a unified AI companion across fitness, study, health,
productivity, and personal well-being domains.

### Design Principles
1. **Privacy-First**: All personal data encrypted at rest. Journal vault uses
   AES-256. Zero telemetry unless explicitly opted in.
2. **Offline-Resilient**: Core scheduling, journal, and habit tracking work
   without internet. Sync when reconnected.
3. **Modular Monolith → Microservices**: Start as a well-structured monolith
   with clean module boundaries. Extract to microservices only when scale demands.
4. **Event-Driven Core**: All modules communicate via an internal event bus.
   This enables loose coupling and audit trails for free.
5. **AI-Augmented, Human-Controlled**: AI suggests, user decides. No autonomous
   actions without explicit consent configuration.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐   │
│  │ React Web│  │React Nat.│  │  Alexa   │  │Telegram/WhApp │   │
│  │   (PWA)  │  │(iOS+And) │  │  Skill   │  │   Bot Layer   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬────────┘   │
└───────┼──────────────┼──────────────┼───────────────┼────────────┘
        │              │              │               │
        ▼              ▼              ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API GATEWAY (Nginx)                        │
│              Rate Limiting · JWT Auth · CORS · SSL              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER (FastAPI)                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    Core Services                           │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │  │
│  │  │   Auth   │ │ Schedule │ │  Health  │ │   Journal    │  │  │
│  │  │ Service  │ │ Engine   │ │ Service  │ │   Vault      │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │  │
│  │  │  Study   │ │ Fitness  │ │  Habits  │ │   Family     │  │  │
│  │  │ Mentor   │ │ Intel    │ │ Tracker  │ │  Ecosystem   │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │  │
│  │  │  Email   │ │  Voice   │ │ Medicine │ │   Trading    │  │  │
│  │  │  Intel   │ │ Handler  │ │ Reminder │ │  Dashboard   │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                   Cross-Cutting Concerns                   │  │
│  │  Event Bus · Audit Logger · Encryption · Rate Limiter      │  │
│  │  Error Handler · Health Check · Metrics · Cache Layer      │  │
│  └────────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  PostgreSQL  │ │    Redis     │ │  Object Store│
│  (Primary)   │ │ (Cache/Queue)│ │ (Encrypted)  │
└──────────────┘ └──────────────┘ └──────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   EXTERNAL INTEGRATIONS                          │
│  Gemini API · OpenRouter · Whisper · Gmail · Outlook            │
│  Alexa Skills Kit · Telegram Bot · WhatsApp Business            │
│  Apple HealthKit · Samsung Health · Noise Watch API             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    N8N WORKFLOW ENGINE                            │
│  Midnight Schedule Regen · Email Digest · Health Sync           │
│  Medicine Reminders · Procrastination Detection                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Module Breakdown

### 3.1 Auth & Identity
- JWT access tokens (15min) + refresh tokens (7d)
- bcrypt password hashing (12 rounds)
- Multi-user family support with role-based access
- Device registration for multi-device sync
- Session management with device fingerprinting

### 3.2 Dynamic Auto-Scheduling
- Midnight regeneration via Gemini API
- Constraint solver: sleep, meals, work, study, exercise
- Priority weighting: urgent > important > routine
- Conflict resolution with user preference learning
- Real-time rescheduling via voice or manual override
- Calendar integration (Google Cal, Apple Cal)

### 3.3 Journal Vault
- AES-256-GCM encryption per entry
- User-derived encryption key (PBKDF2 from passphrase)
- Server cannot read entries (zero-knowledge)
- Full-text search over encrypted entries (client-side)
- Export as encrypted archive

### 3.4 Health & Fitness Intelligence
- Wearable data ingestion (Apple HealthKit, Samsung, Noise)
- OpenRouter AI analysis for health patterns
- Energy level forecasting from sleep + activity data
- Workout plan adaptation based on recovery metrics
- Medicine/supplement reminders (user-configured only)

### 3.5 Study Mentor (IAS Focus)
- Spaced repetition engine
- Subject progress tracking
- Pomodoro with intelligent break scheduling
- Weak area detection from quiz performance
- Study plan integration with main schedule

### 3.6 Habit Tracking & Accountability
- Streak tracking with grace periods
- Procrastination detection via schedule adherence
- Accountability partner notifications
- Habit correlation analysis
- A/B testing framework for habit interventions

---

## 4. Database Design Philosophy

- UUIDs for all primary keys (multi-device sync safety)
- Soft deletes everywhere (deleted_at timestamp)
- Full audit trail (who changed what, when)
- Tenant isolation via user_id foreign keys
- JSONB for flexible metadata fields
- Timestamps in UTC, timezone stored per user

---

## 5. Security Model

| Layer          | Mechanism                              |
|----------------|----------------------------------------|
| Transport      | TLS 1.3 everywhere                     |
| Authentication | JWT + refresh token rotation           |
| Authorization  | RBAC (owner, family_admin, member)     |
| Data at Rest   | AES-256-GCM (journals), pgcrypto (PII) |
| API Security   | Rate limiting, CORS, input validation  |
| Audit          | Immutable append-only audit log        |
| Export         | Encrypted archives, user-controlled    |

---

## 6. Deployment Architecture

**Phase 1 (MVP):** Single Oracle VM + managed PostgreSQL
**Phase 2:** Oracle VM + Google Cloud Run for workers
**Phase 3:** Full Kubernetes on GKE

Docker Compose for local dev. GitHub Actions for CI/CD.
Prometheus + Grafana for monitoring. Sentry for error tracking.
