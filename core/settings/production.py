"""Production settings — set DJANGO_SETTINGS_MODULE=core.settings.production to use these."""

from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured

from core.settings.base import *

DEBUG = False

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set when DEBUG is False.")

# No FRONTEND_URL fallback in production — the browser origin allowlist must be
# stated explicitly.
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", cast=Csv())
if not CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS must be set in production.")

# Behind a trusted proxy that appends X-Forwarded-For.
REQUEST_LOG_TRUST_FORWARDED_FOR = True


# Security hardening — see `manage.py check --deploy`. These reflect a fixed
# HTTPS-only posture, not a per-deployment tunable, so they're hardcoded here
# rather than read from .env (unlike SECURE_HSTS_SECONDS below, which is a
# duration you deliberately ramp up over time as HTTPS rollout is verified).
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# This app is expected to run behind a TLS-terminating reverse proxy/load
# balancer (the standard shape for a containerized deployment) — without
# this, SECURE_SSL_REDIRECT can't tell a proxied HTTPS request from a plain
# HTTP one (the proxy-to-app hop is HTTP) and redirect-loops forever. Only
# trust this header from a proxy that's actually stripping/overwriting any
# client-supplied X-Forwarded-Proto — verify that at the proxy/LB config.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# Static files — compressed, cache-busted filenames via WhiteNoise.
# https://whitenoise.readthedocs.io/en/stable/django.html
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Don't expose the API surface publicly in production — schema + docs are staff-only.
SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.IsAdminUser"]
