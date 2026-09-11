from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission
from rest_framework.settings import api_settings


class SubscriptionRequired(APIException):
    """Raised as ``402`` - distinct from the ``403`` used for permission
    denials, so a client can tell "your organization must pay" from "you may
    not do this". The body carries a stable ``code`` alongside the message."""

    status_code = 402
    default_detail = "Your organization does not have an active subscription."
    default_code = "subscription_inactive"

    def __init__(self):
        super().__init__({"detail": self.default_detail, "code": self.default_code})


class HasActiveSubscription(BasePermission):
    """Denies an authenticated user whose organization has no active
    subscription, with ``402``.

    Anonymous requests and superusers (no organization) pass - this gates paid
    access, not authentication. Views that must stay reachable without a
    subscription (auth, password reset, invitation accept) simply don't include
    this permission.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.organization_id:
            return True

        if not user.organization.active_subscription:
            raise SubscriptionRequired()

        return True


class ExtraPermissionsMixin:
    """Adds view-specific permissions to ``DEFAULT_PERMISSION_CLASSES`` instead
    of replacing them, as setting ``permission_classes`` directly would.

    Declare ``extra_permission_classes`` for a fixed set, or override
    ``get_permissions`` and call ``_permissions_for`` when it varies by
    request. Extras run first - they're cheap attribute checks, while
    ``HasActiveSubscription`` hits the database and shouldn't run for a
    request an extra would deny anyway.
    """

    extra_permission_classes: tuple = ()

    def get_permissions(self):
        return self._permissions_for(*self.extra_permission_classes)

    def _permissions_for(self, *extra_classes):
        classes = (*extra_classes, *api_settings.DEFAULT_PERMISSION_CLASSES)
        return [permission_class() for permission_class in classes]
