from rest_framework.throttling import ScopedRateThrottle

from users.two_factor import InvalidTwoFactorLoginError, login_token_user_id


class TwoFactorLoginThrottle(ScopedRateThrottle):
    """A scoped rate per account being signed in to, not per address, so
    guessing an account's codes from many addresses gets no more tries. A
    request without a genuine sign-in token counts against its address."""

    def get_cache_key(self, request, view):
        data = request.data if isinstance(request.data, dict) else {}
        try:
            ident = f"user-{login_token_user_id(str(data.get('two_factor_token', '')))}"
        except InvalidTwoFactorLoginError:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
