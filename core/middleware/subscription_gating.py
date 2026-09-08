"""Blocks API access when the caller's organization has no active subscription.

DRF's JWT auth runs inside the view, too late to stop a request before it does
work, so this middleware authenticates the bearer token itself (via
``JWTAuthentication``, keeping token revocation and the ``is_active`` check) and
short-circuits with ``402``. ``402`` rather than the ``403`` used for permission
denials, so a client can tell "your organization must pay" from "you may not".
"""

from http import HTTPStatus

from django.conf import settings
from django.http import JsonResponse
from django.urls import Resolver404, resolve
from rest_framework.exceptions import APIException
from rest_framework_simplejwt.authentication import JWTAuthentication

SUBSCRIPTION_REQUIRED_DETAIL = "Your organization does not have an active subscription."
SUBSCRIPTION_REQUIRED_CODE = "subscription_inactive"

_authenticator = JWTAuthentication()


class SubscriptionGatingMiddleware:
    """Returns ``402`` for an authenticated org user with no active subscription.

    Superusers (no organization), unauthenticated callers, and the URL names in
    ``settings.SUBSCRIPTION_GATING_EXEMPT_URL_NAMES`` (auth, password reset,
    invitation accept, operational endpoints) are never gated - those flows must
    stay reachable or an unpaid org can't recover.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._payment_required(request):
            return JsonResponse(
                {
                    "detail": SUBSCRIPTION_REQUIRED_DETAIL,
                    "code": SUBSCRIPTION_REQUIRED_CODE,
                },
                status=HTTPStatus.PAYMENT_REQUIRED,
            )
        return self.get_response(request)

    def _payment_required(self, request):
        if self._is_exempt(request):
            return False

        user = self._authenticated_user(request)
        if user is None:
            return False

        if user.organization_id is None:
            return False

        return user.organization.active_subscription is None

    @staticmethod
    def _is_exempt(request):
        """Whether the resolved URL name is on the allowlist - matched by name,
        never by prefix, so a new endpoint is gated until deliberately exempted."""
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return True
        return match.url_name in settings.SUBSCRIPTION_GATING_EXEMPT_URL_NAMES

    @staticmethod
    def _authenticated_user(request):
        """The user behind this request, or ``None``.

        ``request.user`` isn't populated for JWT this early, so authenticate the
        bearer token directly. A bad token counts as unauthenticated here - the
        view's own auth raises the ``401``.
        """
        existing = getattr(request, "user", None)
        if existing is not None and existing.is_authenticated:
            return existing

        try:
            result = _authenticator.authenticate(request)
        except APIException:
            return None
        return result[0] if result is not None else None
