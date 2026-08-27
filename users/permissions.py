from rest_framework.permissions import BasePermission

from users.choices import OrganizationRole


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
