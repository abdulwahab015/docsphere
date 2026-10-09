FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt requirements.txt
RUN pip install --no-cache-dir --user -r requirements.txt


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

# /home/app/beat holds Celery beat's schedule file and /app/media the attached
# files; a new volume mounted on either starts out owned by app, like the
# directory.
RUN mkdir -p /app/staticfiles /home/app/beat /app/media \
    && chown app:app /app/staticfiles /home/app/beat /app/media

USER app

# collectstatic loads the production settings, which refuse to start without
# their required values - placeholders here; the real ones come at run time.
# A setting added without a default needs a line here too (CI builds this image).
RUN DJANGO_SETTINGS_MODULE=core.settings.production \
    SECRET_KEY=collectstatic-build-time-placeholder \
    ALLOWED_HOSTS=collectstatic \
    CORS_ALLOWED_ORIGINS=https://collectstatic.invalid \
    SECURE_HSTS_SECONDS=0 \
    ACCESS_TOKEN_LIFETIME_SECONDS=900 \
    REFRESH_TOKEN_LIFETIME_SECONDS=604800 \
    INVITATION_EXPIRY_SECONDS=604800 \
    EMAIL_LINK_EXPIRY_SECONDS=86400 \
    SUBSCRIPTION_EXPIRY_REMINDER_DAYS=7 \
    ANON_THROTTLE_RATE=60/min \
    USER_THROTTLE_RATE=1000/min \
    LOGIN_THROTTLE_RATE=10/min \
    TWO_FACTOR_LOGIN_THROTTLE_RATE=5/min \
    INVITE_ACCEPT_THROTTLE_RATE=10/min \
    PASSWORD_RESET_THROTTLE_RATE=5/hour \
    BILLING_CHECKOUT_THROTTLE_RATE=10/min \
    BILLING_PORTAL_THROTTLE_RATE=10/min \
    ORG_SIGNUP_THROTTLE_RATE=5/hour \
    PASSWORD_CHANGE_THROTTLE_RATE=5/hour \
    EMAIL_VERIFICATION_THROTTLE_RATE=10/hour \
    EMAIL_CHANGE_THROTTLE_RATE=5/hour \
    ORGANIZATION_EXPORT_THROTTLE_RATE=5/day \
    STRIPE_PRODUCT_ID=prod_collectstatic-build-time-placeholder \
    python manage.py collectstatic --noinput

# The git commit a release is built from, which error reports name. Last, so
# a new commit doesn't invalidate the layers above.
ARG RELEASE=""
ENV SENTRY_RELEASE=$RELEASE

EXPOSE 8000

CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000"]
