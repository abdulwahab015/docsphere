from rest_framework_simplejwt.authentication import (
    JWTAuthentication as SimpleJWTAuthentication,
)

from core.error_tracking import identify_user


class JWTAuthentication(SimpleJWTAuthentication):
    """SimpleJWT's bearer-token authentication, which also tells error
    tracking whose request it is (ids only). Authentication happens in the
    view, after every middleware has run, so this is the first point at which
    the user is known."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result:
            identify_user(result[0])
        return result
