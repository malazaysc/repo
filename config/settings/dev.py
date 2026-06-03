"""Development settings."""
from .base import *  # noqa: F403
from .base import INSTALLED_APPS, MIDDLEWARE

DEBUG = True

# Enable django-debug-toolbar only when it's installed (it's a dev-group dep,
# so the slim Docker image may not include it).
try:
    import debug_toolbar  # noqa: F401

    INSTALLED_APPS += ["debug_toolbar"]
    MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware", *MIDDLEWARE]
    INTERNAL_IPS = ["127.0.0.1"]
    # In Docker the request IP isn't 127.0.0.1; show the toolbar regardless in dev.
    DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG}
except ImportError:
    pass

# Run Celery tasks synchronously when a worker isn't available (handy for tests).
CELERY_TASK_ALWAYS_EAGER = False
