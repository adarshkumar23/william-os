# WILLIAM OS API Documentation Finalization (Task 6.8)

## Scope
This document finalizes endpoint groups and operational behavior for MVP launch.

## API Envelope
All API responses follow:
- ok: boolean
- data: payload or null
- error: message or null
- meta: optional metadata

## Base Paths
- REST: /api/v1
- WebSocket: /ws/v1/sync
- Health: /health
- Metrics: /metrics

## Module Endpoint Summary

### Authentication
- POST /api/v1/auth/register
- POST /api/v1/auth/login
- POST /api/v1/auth/refresh
- GET /api/v1/auth/me

### Scheduler
- POST /api/v1/schedule/generate
- GET /api/v1/schedule/today
- GET /api/v1/schedule/{date}
- POST /api/v1/schedule/{date}/blocks
- PATCH /api/v1/schedule/blocks/{id}
- POST /api/v1/schedule/blocks/{id}/start
- POST /api/v1/schedule/{date}/reschedule

### Habits
- Habit create/list/check-in endpoints under /api/v1/habits

### Journal
- Encrypted create/read/list endpoints under /api/v1/journal

### Medicine
- Medicine CRUD and logging endpoints under /api/v1/medicine

### Experiments
- GET /api/v1/experiments/assignments

### Export and Privacy
- GET /api/v1/export/summary
- POST /api/v1/export/full
- POST /api/v1/export/journal
- POST /api/v1/export/lifetime
- DELETE /api/v1/export/account

## Realtime Contract
- WebSocket endpoint requires valid access token query parameter.
- Sync message types include:
  - schedule_updated
  - habit_checked_in
  - medicine_logged
  - journal_created
  - block_completed

## Operational Guarantees
- Rate limiting applied on HTTP routes except health/metrics.
- Offline degraded-mode middleware caches GET responses and queues mutations.
- Security headers are attached to responses.
- Request timing is exposed through X-Response-Time-ms.

## OpenAPI
OpenAPI remains source-of-truth for request/response models and can be viewed at:
- /docs (non-production)
- /redoc (non-production)

## Release Notes
This finalization reflects Sprint 5 and Sprint 6 work through launch readiness, including export/privacy, realtime sync, observability, and baseline security automation.
