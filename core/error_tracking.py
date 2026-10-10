"""Reporting unhandled errors to a Sentry-compatible service (Sentry, or a
self-hosted GlitchTip): off unless ``SENTRY_DSN`` is set.

A report says which user and organization it happened to by id only - never
an email, IP address, cookie, token, password or document content. So no
request bodies, headers, cookies or query strings (a search term can be
content) and no local variables from the stack are sent: the request's method
and path, the error and its stack trace are what's left.
"""

import sentry_sdk
from django.conf import settings
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

# The parts of a request a report keeps.
_REQUEST_KEYS_KEPT = ("method", "url")


def scrub_event(event, hint):
    """Keeps only what may leave the server: the request's method and path,
    and the user's id."""
    request = event.get("request")
    if request:
        event["request"] = {
            key: request[key] for key in _REQUEST_KEYS_KEPT if key in request
        }
    user = event.get("user")
    if user:
        event["user"] = {"id": user["id"]} if "id" in user else {}
    return event


def init_error_tracking():
    """Starts reporting errors from Django and Celery, if ``SENTRY_DSN`` is
    set. Returns whether it did."""
    if not settings.SENTRY_DSN:
        return False

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        release=settings.SENTRY_RELEASE or None,
        # Errors only, so Django's signal receivers aren't wrapped to time them.
        integrations=[
            DjangoIntegration(signals_spans=False),
            CeleryIntegration(),
        ],
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        before_send=scrub_event,
    )
    return True


def identify_user(user):
    """Marks the current request's error reports with whose request it was -
    the user's and organization's ids, nothing else."""
    sentry_sdk.set_user({"id": str(user.pk)})
    sentry_sdk.set_tag("organization_id", str(user.organization_id or ""))
