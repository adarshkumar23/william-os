FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# ── Dependencies ─────────────────────────────────────────────────
FROM base AS deps
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install -e ".[dev]"

# ── Production ───────────────────────────────────────────────────
FROM deps AS production
COPY . .

# Non-root user
RUN addgroup --system william && adduser --system --ingroup william william
RUN mkdir -p /app/data && chown -R william:william /app
USER william

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
