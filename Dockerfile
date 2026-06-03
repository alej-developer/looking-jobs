# ==============================================================================
# Dockerfile — Multi-stage optimized build for ATS Job Automator
# Base: Official Playwright image (includes Chromium + system deps)
# ==============================================================================

# ─── Stage 1: Dependency installer ───────────────────────────────────────────
FROM mcr.microsoft.com/playwright/python:v1.52.0-noble AS builder

WORKDIR /build

# Copy only requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies into a clean prefix
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── Stage 2: Production runtime ─────────────────────────────────────────────
FROM mcr.microsoft.com/playwright/python:v1.52.0-noble AS runtime

# Metadata
LABEL maintainer="alej-developer"
LABEL description="ATS Job Automator — Stealth scraper for corporate ATS portals"
LABEL version="0.1.0"

# Security: run as non-root user
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid 1001 --create-home appuser

WORKDIR /app

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source code
COPY config.py main.py database.py parser.py scraper.py benchmark.py ./
COPY src/ ./src/
COPY .env.example ./.env.example

# Create data directory for the persistent SQLite volume
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# ─── Persistent Volume ──────────────────────────────────────────────────────
# Mount this volume so jobs_automation.db survives container restarts:
#   docker run -v ats_data:/app/data ...
VOLUME ["/app/data"]

# Install only Chromium (no Firefox/WebKit — saves ~800MB)
RUN playwright install chromium --with-deps 2>/dev/null || true

# Switch to non-root user
USER appuser

# Environment defaults (override via docker run -e or .env mount)
ENV APP_ENV=production
ENV LOG_LEVEL=INFO
ENV HEADLESS_MODE=true
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check: verify Python and Playwright are functional
HEALTHCHECK --interval=60s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import playwright; import database; print('OK')" || exit 1

# Default entrypoint
ENTRYPOINT ["python"]
CMD ["main.py"]
