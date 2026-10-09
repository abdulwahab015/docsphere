from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission

from users.choices import OrganizationRole


class EmailNotVerified(APIException):
    """Raised as ``403`` with a stable ``code``, so a client can tell "verify
    your email first" from any other refusal and show the right screen."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Verify your email address to continue."
    default_code = "email_unverified"

    def __init__(self):
        super().__init__({"detail": self.default_detail, "code": self.default_code})


class HasVerifiedEmail(BasePermission):
    """Denies a signed-in user who hasn't verified their email address yet,
    with ``403`` ``email_unverified``. Until they do, they may only verify,
    ask for a new link, read their own account and log out - so someone who
    signs up with another person's address can't do anything with it.

    Anonymous requests pass: authentication is another permission's job.
    Listed before ``HasActiveSubscription``, so a new organization learns it
    must verify before it learns it must subscribe.
    """

    def has_permission(self, request, view):
        user = request.user
        if user and user.is_authenticated and not user.email_verified:
            raise EmailNotVerified()
        return True


class TwoFactorRequired(APIException):
    """Raised as ``403`` with a stable ``code``, so a client can tell "set up
    two-factor sign-in first" from any other refusal."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = (
        "Your organization requires two-factor sign-in. Set it up to continue."
    )
    default_code = "two_factor_required"

    def __init__(self):
        super().__init__({"detail": self.default_detail, "code": self.default_code})


class MeetsTwoFactorRequirement(BasePermission):
    """Denies a signed-in user whose organization requires two-factor sign-in
    while they haven't set it up, with ``403`` ``two_factor_required``. Until
    they do, they may only set it up, read their own account and log out.

    Listed right after ``HasVerifiedEmail``, before the organization's
    deletion and subscription checks."""

    def has_permission(self, request, view):
        user = request.user
        if user and user.is_authenticated and user.needs_two_factor_setup:
            raise TwoFactorRequired()
        return True


class IsOrganizationAdmin(BasePermission):
    """Allows access only to authenticated users who are an ADMIN within their
    own organization."""

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.organization_id
            and user.org_role == OrganizationRole.ADMIN
        )
