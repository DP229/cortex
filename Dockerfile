FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt setup.py README.md ./
COPY cortex/ ./cortex/
COPY cortex_cli/ ./cortex_cli/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e . && \
    pip install --no-cache-dir psycopg2-binary alembic requests email-validator

# Ensure data directories exist (root, so no write permission issues)
RUN mkdir -p /app/data /app/wiki /app/raw /app/.cortex /app/logs

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    DATABASE_URL=sqlite:///app/data/cortex.db \
    WORKERS=4

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=5 \
    CMD curl -sf http://localhost:8080/health || exit 1

CMD uvicorn cortex.api:app --host 0.0.0.0 --port 8080 --workers ${WORKERS} --proxy-headers --forwarded-allow-ips '*'
