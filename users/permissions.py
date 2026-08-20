from rest_framework.permissions import BasePermission

from users.choices import OrganizationRole


class IsOrgAdmin(BasePermission):
    """Allows access only to authenticated users with an ADMIN org_role
    who belong to an organization (excludes org-less platform admins)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.organization_id is not None
            and user.org_role == OrganizationRole.ADMIN
        )
