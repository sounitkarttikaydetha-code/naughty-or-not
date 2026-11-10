# Multi-stage Dockerfile for Naughty or not (Sanction checK)
# Stage 1: Build & wheels preparation
FROM python:3.14-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock ./
# Pre-install wheels without compiling at runtime
RUN pip install --no-cache-dir --upgrade pip wheel && \
    pip wheel --no-cache-dir --wheel-dir=/build/wheels -r requirements.lock

# Stage 2: Hardened, non-root runtime
FROM python:3.14-slim AS runtime

# Security: Non-root user with explicit UID/GID
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/false -m -d /home/appuser appuser

WORKDIR /app

# Install wheels from builder stage
COPY --from=builder /build/wheels /wheels
COPY requirements.lock ./
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.lock && \
    rm -rf /wheels requirements.lock

# Copy application source code (no data, caches, or secrets)
COPY app.py ./
COPY modules/ ./modules/
COPY config/ ./config/
COPY static/ ./static/

# Create runtime state directories with appropriate non-root ownership
RUN mkdir -p /app/data /app/logs /app/reports /app/cache && \
    chown -R appuser:appgroup /app /home/appuser

# Environment configuration for server mode
ENV DEPLOYMENT_MODE=server \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NAUGHTY_DATA_DIR=/app/data \
    NAUGHTY_LOGS_DIR=/app/logs \
    NAUGHTY_REPORTS_DIR=/app/reports \
    NAUGHTY_CACHE_DIR=/app/cache \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Drop privileges
USER 10001:10001

EXPOSE 8501

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health').read()" || exit 1

ENTRYPOINT ["streamlit", "run", "app.py"]
