from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission


class SubscriptionRequired(APIException):
    """Raised as ``402`` - distinct from the ``403`` used for permission
    denials, so a client can tell "your organization must pay" from "you may
    not do this". The body carries a stable ``code`` alongside the message."""

    status_code = 402
    default_detail = "Your organization does not have an active subscription."
    default_code = "subscription_inactive"

    def __init__(self):
        super().__init__({"detail": self.default_detail, "code": self.default_code})


class OrganizationDeleted(APIException):
    """Raised as ``403`` with its own ``code``: the caller's organization has
    been deleted and is waiting to be purged, so nobody in it may use the app
    - its admins may only restore it."""

    status_code = 403
    default_detail = "Your organization has been deleted."
    default_code = "organization_deleted"

    def __init__(self):
        super().__init__({"detail": self.default_detail, "code": self.default_code})


class HasActiveSubscription(BasePermission):
    """Denies an authenticated user whose organization has no active
    subscription, with ``402``.

    A deleted organization is refused before that, with ``403``
    ``organization_deleted``. Anonymous requests and superusers (no
    organization) pass - this gates paid access, not authentication. Views that must stay reachable without a
    subscription (auth, password reset, invitation accept) simply don't include
    this permission.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.organization_id:
            return True

        if user.organization.deletion_requested_at:
            raise OrganizationDeleted()
        if not user.organization.active_subscription:
            raise SubscriptionRequired()

        return True
