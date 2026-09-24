"""Test settings — used by CI for a fast, deterministic run.

Set DJANGO_SETTINGS_MODULE=core.settings.test. Falls back to base.py's own
sqlite default for DATABASE_URL, so CI needs no database service.
"""

from core.settings.base import *

DEBUG = False

# Quiet the per-request INFO logging during the suite — tests that assert on
# it use `assertLogs`, which forces the level it needs regardless.
LOGGING["loggers"]["core"]["level"] = "WARNING"

# Rates high enough that only the tests that explicitly exercise throttling
# (via patch.object on THROTTLE_RATES) ever hit a 429.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = dict.fromkeys(
    ("anon", "user", "login", "invite_accept", "password_reset"), "100000/min"
)

# Tests must not depend on the ambient CELERY_TASK_ALWAYS_EAGER value from
# .env — force it here so async-path tests are deterministic regardless of
# environment. (Individual test classes still set this explicitly too, per
# the project convention — this is just a safe baseline.)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Trade password-hashing security for speed — this process never touches
# real user data, and user creation happens constantly across the suite.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
