"""Production settings."""
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env

DEBUG = False

# Require a real secret key in prod — never fall back to the dev sentinel (S5).
SECRET_KEY = env("DJANGO_SECRET_KEY")
if SECRET_KEY == "dev-insecure-change-me":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a secure, unique value in production.")

# Hosts must be set explicitly in prod (S9).
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
