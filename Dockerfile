# syntax=docker/dockerfile:1

FROM python:3.14-slim AS base

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

# System deps:
#  - build-essential/libpq: psycopg & native builds
#  - ffmpeg: yt-dlp media handling (optional but commonly needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (better layer caching).
COPY pyproject.toml ./
# uv.lock is optional on first build; copy if present.
COPY uv.loc[k] ./
RUN uv sync --no-install-project --no-dev

# Copy the application
COPY . .

EXPOSE 8000

# Default command is overridden by docker-compose per-service.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
