# Sentinel collector & API server.
# Build context is the repository root (see docker-compose.yml) so we can pull
# in the sibling evaluators package.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the local evaluators package first, then the server (incl. postgres
# driver). Copying pyproject files separately keeps Docker layer caching useful.
COPY packages/evaluators /app/packages/evaluators
COPY server /app/server

RUN pip install --upgrade pip \
    && pip install ./packages/evaluators \
    && pip install "./server[postgres]"

# Run as a non-root user.
RUN useradd --create-home --uid 10001 sentinel \
    && mkdir -p /data && chown -R sentinel /data /app
USER sentinel

ENV SENTINEL_DATABASE_URL="sqlite+aiosqlite:////data/sentinel.db"
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["sentinel-server", "--host", "0.0.0.0", "--port", "8000"]
