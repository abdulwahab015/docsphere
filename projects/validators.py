from rest_framework.exceptions import ValidationError

from projects.choices import AccessLevel


def ensure_not_last_owner(permission, permission_model, resource_field, resource):
    """A resource's last Owner-level grant can't be revoked, so it never ends
    up with nobody able to manage its sharing."""
    if permission.access_level != AccessLevel.OWNER:
        return

    owner_count = permission_model.objects.filter(
        access_level=AccessLevel.OWNER, **{resource_field: resource}
    ).count()
    if owner_count <= 1:
        raise ValidationError(
            {"detail": f"Cannot revoke the {resource_field}'s last Owner."}
        )
