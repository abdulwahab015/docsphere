import json
import logging
import re
import uuid

from django.conf import settings

logger = logging.getLogger("core.request")

# Response keys whose values must never reach the logs (JWTs, reset tokens, ...).
_SENSITIVE_KEYS = frozenset(
    {"access", "refresh", "token", "password", "new_password", "uid"}
)

# Catch a token that slips through under an unexpected key (JWT shape).
_JWT_RE = re.compile(r"^eyJ[\w-]+\.[\w-]+\.[\w-]+$")


def _redact(value):
    """Recursively replace sensitive values, keeping the structure intact."""
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key in _SENSITIVE_KEYS else _redact(inner)
            for key, inner in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and _JWT_RE.match(value):
        return "[redacted]"
    return value


class RequestLoggingMiddleware:
    """Logs one line per request and one per response, correlated by a
    generated ``request_id``.

    Sensitive response keys are redacted; JSON bodies are then truncated to
    ``settings.MAX_LOG_BODY_CHARS`` so the logs stay readable; non-JSON bodies
    are not logged at all. Paths in ``settings.REQUEST_LOG_SKIP_PATHS`` (health
    probes) are skipped entirely.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in settings.REQUEST_LOG_SKIP_PATHS:
            return self.get_response(request)

        request_id = uuid.uuid4().hex
        request.request_id = request_id

        context = {
            "request_id": request_id,
            "method": request.method,
            "path": request.path,
            "client_ip": self._client_ip(request),
        }

        logger.info("request started", extra=context)

        response = self.get_response(request)

        user = getattr(request, "user", None)
        context["status_code"] = response.status_code
        context["user_id"] = (
            getattr(user, "id", None)
            if getattr(user, "is_authenticated", False)
            else None
        )

        logger.info(
            "request finished %s",
            self._response_body(response),
            extra=context,
        )

        return response

    @staticmethod
    def _client_ip(request):
        """The peer address. When behind a trusted proxy (see
        ``REQUEST_LOG_TRUST_FORWARDED_FOR``), use the right-most
        X-Forwarded-For entry — the one the proxy itself appended — since
        everything to its left is client-supplied and spoofable."""
        if settings.REQUEST_LOG_TRUST_FORWARDED_FOR:
            forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
            if forwarded:
                return forwarded.split(",")[-1].strip()
        return request.META.get("REMOTE_ADDR", "")

    @staticmethod
    def _response_body(response):
        if "application/json" not in response.get("content-type", "") or not hasattr(
            response, "data"
        ):
            return "-"

        body = json.dumps(_redact(response.data), default=str)
        limit = settings.MAX_LOG_BODY_CHARS
        return body if len(body) <= limit else f"{body[:limit]}…"
