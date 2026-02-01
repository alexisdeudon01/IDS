# ============================================================================
# IDS2 SOC Pipeline - Python Agent Dockerfile
# Multi-stage build for Raspberry Pi 5 (ARM64)
# ============================================================================

FROM python:3.11-slim-bookworm AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libssl-dev \
    libffi-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first (for layer caching)
COPY python_env/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ============================================================================
# Production stage
# ============================================================================
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app:${PATH}"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash ids2 && \
    mkdir -p /app /mnt/ram_logs && \
    chown -R ids2:ids2 /app /mnt/ram_logs

# Set working directory
WORKDIR /app

# Copy Python packages from base stage
COPY --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=ids2:ids2 python_env/ ./python_env/
COPY --chown=ids2:ids2 config.yaml .
COPY --chown=ids2:ids2 vector/ ./vector/
COPY --chown=ids2:ids2 suricata/ ./suricata/

# Create necessary directories
RUN mkdir -p /app/logs /app/.git && \
    chown -R ids2:ids2 /app

# Switch to non-root user
USER ids2

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:9100/metrics || exit 1

# Expose ports
EXPOSE 9100

# Set entrypoint
ENTRYPOINT ["python3", "/app/python_env/agent_mp.py"]
