"""drf-spectacular postprocessing hook.

``SubscriptionGatingMiddleware`` can return ``402`` on any endpoint that isn't
on the gating allowlist, but it's middleware - no view declares that response.
This hook adds it to every non-exempt operation in the generated schema so the
documented contract matches what a client can actually receive.
"""

import re

from django.conf import settings
from django.urls import Resolver404, resolve

_PATH_PARAM_RE = re.compile(r"\{[^}]+\}")

_HTTP_METHODS = frozenset(
    {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
)

_PAYMENT_REQUIRED_RESPONSE = {
    "description": "The authenticated user's organization has no active subscription.",
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "properties": {
                    "detail": {"type": "string"},
                    "code": {"type": "string", "enum": ["subscription_inactive"]},
                },
            }
        }
    },
}


def _url_name(openapi_path):
    """Resolve an OpenAPI path (``/api/v1/users/{id}/deactivate/``) back to its
    URL name, substituting a dummy value for path parameters."""
    try:
        return resolve(_PATH_PARAM_RE.sub("1", openapi_path)).url_name
    except Resolver404:
        return None


def add_subscription_gate_responses(result, generator, request, public):
    exempt = settings.SUBSCRIPTION_GATING_EXEMPT_URL_NAMES
    for path, path_item in result.get("paths", {}).items():
        name = _url_name(path)
        if name is None or name in exempt:
            continue
        for method, operation in path_item.items():
            if method.lower() in _HTTP_METHODS:
                operation.setdefault("responses", {}).setdefault(
                    "402", _PAYMENT_REQUIRED_RESPONSE
                )
    return result
