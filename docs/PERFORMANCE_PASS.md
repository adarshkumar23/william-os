# WILLIAM OS Performance Pass (Task 6.6)

## Scope
- Date: 2026-04-06
- Goal: ensure MVP remains responsive under expected early-load profile and has observability hooks for tuning.

## Implemented Optimizations
- Redis sliding-window rate limiting with burst allowance.
- Offline fallback middleware with cached GET responses during degraded mode.
- WebSocket sync fan-out for multi-device updates (reduces polling pressure).
- Request timing header (`X-Response-Time-ms`) for quick latency sampling.
- Prometheus `/metrics` exposure via instrumentator.
- Grafana auto-provisioned datasource and overview dashboard template.

## Load Test Profiles
1. Smoke profile:
```bash
bash scripts/performance-smoke.sh http://localhost:8000 25 5 2m
```

2. Target profile (Sprint objective):
```bash
make test-load-100
```

## Operational Metrics To Watch
- HTTP p95 / p99 latency
- 429 rate-limit response ratio
- Redis error/warning rate in logs
- Celery queue depth and task runtime
- DB connection pool utilization

## Pass/Fail Guidance
- p95 latency should remain stable under target profile for core endpoints.
- Error ratio should stay low and non-5xx errors should be dominated by expected auth/rate-limit flows.
- WebSocket connect/disconnect behavior should remain consistent under multi-device activity.

## Follow-Up
- Add Grafana dashboard JSON provisioning for key latency/error widgets.
- Add periodic synthetic load run in CI/staging before release cuts.
