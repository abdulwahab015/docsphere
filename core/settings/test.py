"""Test settings — used by CI for a fast, deterministic run.

Set DJANGO_SETTINGS_MODULE=core.settings.test. Falls back to base.py's own
sqlite default for DATABASE_URL, so CI needs no database service.
"""

from core.settings.base import *

DEBUG = False

LOGGING["loggers"]["core"]["level"] = "WARNING"

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = dict.fromkeys(
    (
        "anon",
        "user",
        "login",
        "invite_accept",
        "password_reset",
        "billing_checkout",
        "org_signup",
    ),
    "100000/min",
)

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
