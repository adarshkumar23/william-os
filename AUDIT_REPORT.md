# WILLIAM OS — Full Audit + Fix Package
**Repo:** `github.com/adarshkumar23/william-os` · **Date:** 2026-04-17 · **Coverage:** 100%

All 27 modules, 17 migrations, CI, compose, Dockerfile, Makefile, frontend auth flow, `.env.example`, `.gitignore`, tests.

## Critical (10)
| # | File | Line | Issue |
|---|------|------|-------|
| C1 | `.github/workflows/ci.yml` | 34, 87 | 8-space indent vs 6 — invalid YAML, scan steps skipped |
| C2 | `core/permissions.py` | 125-133 | Missing/invalid auth bypasses scope enforcement |
| C3 | `auth/routes.py` | 290-305, 69-80 | API keys stored in plaintext (column name lies) |
| C4 | `journal/service.py` | 184-191 | Unlock-probe always succeeds for new users — any passphrase unlocks |
| C5 | `journal/service.py` | 39, 350 | Per-user passphrases cached under global master key + plaintext dict |
| C6 | `chat/executor.py` | 95, 143, 199 | Wrong method names + missing `UTC` import → runtime errors |
| C7 | `chat/executor.py` | 109-115, 157-165, 176-180, 195, 225-229 | Returns ✅ for actions that never persist |
| C8 | `backend/requirements.txt` | — | 4 unpinned packages contradict pyproject (~40) |
| C9 | `docker-compose.yml` | 51, 85, 105 | Public IP hardcoded in CORS |
| C10 | `frontend/.../api.ts` | 84-99 | Access token in localStorage (XSS-stealable) |

## High (16)
H1. **Zero retry logic** across all 17 external-API services. H2. `get_db()` auto-commits. H3. `init_db()` bypasses Alembic in dev. H4. Rate limiter MGETs 61 keys/request. H5. Rate limiter relies on `decode_token` raising HTTPException. H6. Scheduler crashes on unknown Gemini category. H7. Scheduler uses `date.today()` for overnight block duration. H8. Midnight beat uses UTC — breaks for IST users. H9. Offline fallback double-dispatches via ASGI transport. H10. Offline replay uses expired JWTs. H11. Offline cache per-process. H12. No task dedup, no `IntegrityError` handling. H13. Event bus not persisted — audit has gaps on crash. H14. `response.json()` raises on HTML error pages. H15. `audit/service.py` drops unmapped events silently, has dead code. H16. Pervasive `datetime.now(UTC).replace(tzinfo=None)` — naive datetimes in DB; `voice/service.py:205` logs meds at UTC time for IST users.

## Medium (21)
M1. `security.py` drifted from `.bak` — hardcoded `["HS256"]`, HTTPException raised from core.
M2. `docker-compose.yml` obsolete `version:` key.
M3. n8n container no auth.
M4. Grafana fallback password literal `changeme_in_production`.
M5. Dockerfile production stage ships `[dev]` deps.
M6. Stale files in repo: `.bak`, `.new`, `.patch`, `.tmp`.
M7. `.gitignore` missing `*.bak`, `*.tmp`, `*.new`, `*.patch`, `*.tsbuildinfo`.
M8. Makefile `db-reset` drops 15 of 20 schemas.
M9. `init-schemas.sql` missing schemas for calendar/briefing/chat/feed/experiments/export/integrations/secrets.
M10. Tests use SQLite with all schemas→None; raw-SQL routes can't execute; FK checks off.
M11. 125 tests for 18k LOC; no coverage for ScopeEnforcement, API keys, journal unlock, offline replay.
M12. `.env.example` Gemini model name drifts from config default.
M13. No `IntegrityError` handling in habits/medicine/scheduler.
M14. `william_b2_001` partial index uses string literal `'archived'`.
M15. Journal summary → prompt injection surface.
M16. Chat executor actions not audited.
M17. `auth/routes.py:292` API-key create takes `payload: dict` — no Pydantic.
M18. `scheduler/service.py:541-547` prompt interpolates user prose.
M19. `integrations/service_impl.py:11` imports from `auth.routes` — layering violation.
M20. `chat/service.py:551-554` Gemini streaming prefix-assumption double-counts non-prefix chunks.
M21. `export/service.py` naive `datetime.now()` in timestamps.

## Clean
Migration DAG clean (17 revs, linear, symmetric). AES-256-GCM primitives correct. Webhook delivery has proper HMAC + exponential backoff. Pydantic prod validators reject insecure defaults. Bcrypt 72-byte truncation correct. Passlib config correct. WebSocket sync broadcaster solid. Event bus fan-out handles partial failures correctly.

## Patches
`patches/` folder contains surgical fixes for C1-C10 + H1 (central AI helper with retries) + H2 + H4 + H5. See `patches/APPLY.md`.
