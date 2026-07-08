FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

FROM base AS builder
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

FROM base AS runtime
COPY --from=builder /install /usr/local
# Copy the whole service in one layer (.dockerignore trims junk). Robust against
# per-file COPY cache issues and keeps app/, alembic/, alembic.ini together.
COPY . .
RUN useradd -r -s /bin/false gateway
USER gateway
# Render assigns $PORT (default 10000); locally / docker-compose it falls back to 8000.
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,httpx; httpx.get('http://localhost:'+os.getenv('PORT','8000')+'/api/v1/health/live').raise_for_status()"
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4 --loop uvloop --access-log
