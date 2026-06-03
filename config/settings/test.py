"""Test settings.

Runs against the same Postgres as dev (so Postgres-only features like
full-text search are exercised) but with Celery in eager mode and fast,
insecure password hashing. pytest-django creates an isolated ``test_*`` DB.

Run locally against the dockerized Postgres (port-mapped to localhost):
    DATABASE_URL=postgres://repo:repo@localhost:5432/repo uv run pytest
"""
import tempfile

from .base import *  # noqa: F403
from .base import STORAGES

DEBUG = False

# Celery runs inline so ingest_note executes synchronously in tests.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Pin env-driven feature flags so tests don't depend on the developer's .env.
# Tests that exercise these override them explicitly.
AI_SUMMARY_ENABLED = False
CLIP_TOKEN = "test-clip-token"

# Faster hashing in tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Isolate any file writes (attachment downloads, etc.).
MEDIA_ROOT = tempfile.mkdtemp(prefix="repo-test-media-")

# Plain static storage in tests — the manifest backend needs collectstatic.
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
