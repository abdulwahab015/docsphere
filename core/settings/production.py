"""Production settings — set DJANGO_SETTINGS_MODULE=core.settings.production to use these."""

from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured

from core.settings.base import *

DEBUG = False

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set when DEBUG is False.")

CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", cast=Csv())
if not CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS must be set in production.")

REQUEST_LOG_TRUST_FORWARDED_FOR = True

# Sent through the EMAIL_HOST server; the development default only prints them.
EMAIL_BACKEND = config(
    "EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend"
)

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
REFRESH_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Setting STORAGES replaces Django's default for every entry, so "default"
# (where attached files are stored, in MEDIA_ROOT) has to be named too.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.IsAdminUser"]
