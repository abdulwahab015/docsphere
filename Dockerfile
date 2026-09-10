# ---- builder: compiles wheels that need gcc/libpq-dev, discarded after ----
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt requirements.txt
RUN pip install --no-cache-dir --user -r requirements.txt


# ---- runtime: slim image, non-root user, gunicorn by default ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/app/.local/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app

WORKDIR /app

COPY --from=builder --chown=app:app /root/.local /home/app/.local
COPY --chown=app:app . .

# staticfiles/ is .dockerignore'd (collected fresh below, not shipped from
# the build context), so it never gets created by the COPY above — make it
# ourselves, owned by app, before collectstatic runs as that user.
RUN mkdir -p /app/staticfiles && chown app:app /app/staticfiles

USER app

# Placeholder values scoped to this one RUN layer only (not baked in as image
# ENV) so collectstatic's settings import succeeds at build time, without a
# misconfigured runtime container silently falling back to them — a real
# deployment without real env vars still fails loudly instead of booting
# insecurely.
RUN DJANGO_SETTINGS_MODULE=core.settings.production \
    SECRET_KEY=collectstatic-build-time-placeholder \
    ALLOWED_HOSTS=collectstatic \
    CORS_ALLOWED_ORIGINS=https://collectstatic.invalid \
    SECURE_HSTS_SECONDS=0 \
    ACCESS_TOKEN_LIFETIME_SECONDS=900 \
    REFRESH_TOKEN_LIFETIME_SECONDS=604800 \
    INVITATION_EXPIRY_SECONDS=604800 \
    ANON_THROTTLE_RATE=60/min \
    USER_THROTTLE_RATE=1000/min \
    LOGIN_THROTTLE_RATE=10/min \
    INVITE_ACCEPT_THROTTLE_RATE=10/min \
    PASSWORD_RESET_THROTTLE_RATE=5/hour \
    python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000"]
