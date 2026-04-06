# WILLIAM OS Privacy Audit (Task 6.4)

## Scope
- Date: 2026-04-06
- Scope: Backend API, persistence layers, export/delete workflows, third-party AI integrations.
- Objective: Validate data minimization, encryption, user control, and data deletion/export guarantees.

## Data Inventory
| Category | Source | Storage | Protection | Retention |
|---|---|---|---|---|
| Auth credentials | user registration/login | PostgreSQL `auth.users` | bcrypt hash | until account deletion |
| Refresh sessions | device login | PostgreSQL `auth.user_devices` | hashed refresh tokens | rotation + deletion |
| Journal content | journal module | PostgreSQL `journal.journal_entries` | AES-256-GCM encrypted content | until user deletion |
| Schedule/habit/medicine records | app usage | PostgreSQL per-module schemas | DB access controls + audit log | until user deletion |
| Event/audit logs | system actions | PostgreSQL `audit.audit_logs` | append-only model + controlled write paths | until user deletion/system policy |
| Cached offline mutations | degraded mode | local queue JSONL | local filesystem only | replayed then removed |

## Data Flow Review
1. Client to API:
- JWT-authenticated API calls over HTTPS in production.
- Security headers added by middleware.

2. API to storage:
- Module-scoped tables in PostgreSQL.
- Journal payload is encrypted before persistence.

3. API to third-party AI:
- Integrations abstracted by modules.
- Sensitive journal plaintext is not exported to third-party models by default module contracts.

4. User control surfaces:
- `GET /api/v1/export/summary`
- `POST /api/v1/export/full`
- `POST /api/v1/export/journal`
- `POST /api/v1/export/lifetime` (encrypted JSON+CSV)
- `DELETE /api/v1/export/account`

## Verification Performed
- Unit and integration tests validate export/deletion behavior.
- Deletion flow verifies post-delete record counts and writes a system-level `data.delete` audit entry.
- Lifetime export validated with decryptability checks in integration tests.

## Findings
- PASS: Encrypted journal storage and export workflow implemented.
- PASS: User self-service export and delete controls present and tested.
- PASS: Deletion verification step prevents silent partial deletion.
- ACTION: keep JWT secret >= 32 bytes in all non-test environments to remove weak-key warnings.

## Follow-Up Recommendations
- Add formal data retention policy intervals per dataset.
- Add periodic automated privacy regression checks in CI for export/delete endpoints.
