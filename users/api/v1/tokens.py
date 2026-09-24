"""Issuing JWT pairs over HTTP, and the HttpOnly cookie that carries the
refresh token.

Every endpoint that logs a user in returns the pair in the body (unchanged v1
contract) *and* sets the refresh token as an HttpOnly cookie scoped to the
auth endpoints, so a browser client can keep it out of JavaScript's reach and
never persist it itself. The refresh and logout endpoints read the cookie when
the body carries no token.
"""

from django.conf import settings
from rest_framework.response import Response
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken


def set_refresh_cookie(response, refresh):
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        str(refresh),
        max_age=int(jwt_settings.REFRESH_TOKEN_LIFETIME.total_seconds()),
        path=settings.REFRESH_COOKIE_PATH,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


def clear_refresh_cookie(response):
    response.delete_cookie(
        settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


def refresh_token_from(request):
    """The refresh token from the request body, falling back to the cookie."""
    return request.data.get("refresh") or request.COOKIES.get(
        settings.REFRESH_COOKIE_NAME
    )


def token_pair_response(user, status_code):
    """A fresh JWT pair for ``user`` in the body, plus the refresh cookie."""
    refresh = RefreshToken.for_user(user)
    response = Response(
        {"access": str(refresh.access_token), "refresh": str(refresh)},
        status=status_code,
    )
    set_refresh_cookie(response, refresh)
    return response
