## Production Dockerfile for FastAPI backend using uv (Astral)
## - Caches deps via multi-stage build
## - Installs from pyproject.toml (preferred) or falls back to requirements.txt
## - Runs as non-root user

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	UV_LINK_MODE=copy \
	PIP_DISABLE_PIP_VERSION_CHECK=1 \
	PYTHONIOENCODING=UTF-8 \
	TZ=UTC

# Install system dependencies
RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
	   curl ca-certificates build-essential \
	&& rm -rf /var/lib/apt/lists/*

# Install uv (Astral)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
	&& /root/.local/bin/uv --version

WORKDIR /app

# --- Dependencies stage (caching) ---
FROM base AS deps

# Copy only dependency manifests for better caching
COPY pyproject.toml ./
# Copy optional lockfile if present; build won't fail if missing
COPY uv.lock* ./
COPY requirements.txt* ./

# Prefer pyproject with uv sync; fall back to requirements if needed
RUN set -eux; \
	if [ -f pyproject.toml ]; then \
		/root/.local/bin/uv sync --frozen --no-dev --system; \
	elif [ -f requirements.txt ]; then \
		/root/.local/bin/uv pip install --system -r requirements.txt; \
	else \
		echo "No dependency manifest found"; \
	fi

# --- Runtime stage ---
FROM base AS runtime

# Create non-root user
RUN adduser --disabled-password --gecos "app user" appuser \
	&& mkdir -p /app \
	&& chown -R appuser:appuser /app

WORKDIR /app

# Copy installed site-packages from deps stage
COPY --from=deps /usr/local /usr/local

# Copy application source
COPY . ./

# Expose port
EXPOSE 8000

# Environment configuration
ENV APP_MODULE=main:app \
	HOST=0.0.0.0 \
	PORT=8000 \
	LOG_LEVEL=info

# Healthcheck using curl to /health if router exists
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
	CMD curl -fsS http://localhost:${PORT}/health || exit 1

USER appuser

# Use uvicorn for production. Adjust workers via UVICORN_WORKERS if needed.
ENV UVICORN_WORKERS=1
CMD [ \
  "python", "-m", "uvicorn", \
  "main:app", \
  "--host", "0.0.0.0", \
  "--port", "8000", \
  "--log-level", "info" \
]

