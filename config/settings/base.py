"""Base settings shared by all environments."""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
)
# Load .env if present (no-op in containers where vars come from env_file).
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "0.0.0.0"]
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Third party
    # Local
    "core",
    "notes",
    "ingestion",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://repo:repo@db:5432/repo",
    ),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static & media
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Don't let browsers MIME-sniff responses (defense for served media; see S7).
SECURE_CONTENT_TYPE_NOSNIFF = True

# Auth redirects (single-user login)
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "notes:dashboard"
LOGOUT_REDIRECT_URL = "login"

# Celery
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://redis:6379/1")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 600
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# YouTube transcript language preference (priority order). Falls back to any
# available transcript in its own language if none of these match.
YOUTUBE_TRANSCRIPT_LANGUAGES = env.list(
    "YOUTUBE_TRANSCRIPT_LANGUAGES", default=["en", "es"]
)

# X / Twitter — scraped via an authenticated headless browser (Playwright).
# Capture a session first:  python manage.py capture_x_session
X_PARSER_ENABLED = env.bool("X_PARSER_ENABLED", default=False)
X_STORAGE_STATE_PATH = env(
    "X_STORAGE_STATE_PATH", default=str(BASE_DIR / "secrets" / "x_storage_state.json")
)
X_HEADLESS = env.bool("X_HEADLESS", default=True)

# AI summaries (Claude)
AI_SUMMARY_ENABLED = env.bool("AI_SUMMARY_ENABLED", default=False)
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
AI_SUMMARY_MODEL = env("AI_SUMMARY_MODEL", default="claude-haiku-4-5-20251001")
