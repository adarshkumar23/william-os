# WILLIAM OS Security Audit (Task 6.5)

## Scope
- Date: 2026-04-06
- Scope: API auth paths, middleware protections, rate limiting, websocket auth, export/delete operations.
- Goal: basic penetration-test style verification for MVP readiness.

## Controls Reviewed
- JWT auth + refresh flow
- Password hashing via bcrypt
- Journal encryption/decryption via AES-256-GCM
- Redis-backed rate limiting middleware
- Offline/degraded-mode guards
- Security response headers middleware
- WebSocket token authentication

## Penetration Basics Checklist
1. Unauthenticated access
- Attempt: `GET /api/v1/auth/me` without token
- Expected: `401/422`

2. Token tampering
- Attempt: modified bearer token
- Expected: rejection through auth decoding path

3. Rate-limit abuse
- Attempt: repeated unauth/auth burst calls
- Expected: `429` with `Retry-After`

4. WebSocket unauthorized connection
- Attempt: connect `/ws/v1/sync` without/invalid token
- Expected: policy-violation close

5. Security headers present
- Validate: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, CSP

6. Data deletion integrity
- Validate: account delete removes user-scoped data and records system audit event

## How To Run
- Scripted baseline checks:
```bash
bash scripts/security-audit-basics.sh http://localhost:8000
```

- Focused automated tests:
```bash
cd backend
pytest tests/unit/test_rate_limit.py tests/unit/test_websocket.py tests/unit/test_export.py -q
```

## Findings
- PASS: baseline auth rejection and websocket auth guard paths are implemented.
- PASS: rate limiting and security headers middleware are integrated in app startup.
- PASS: export/delete paths have verification tests.
- ACTION: rotate test JWT secret in CI to a >=32-byte value for stronger default hygiene.
- PASS: periodic dependency vulnerability scan (`pip-audit`) is configured in CI (non-blocking).
