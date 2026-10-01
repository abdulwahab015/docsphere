from rest_framework.exceptions import ValidationError

from projects.choices import AccessLevel


def ensure_not_last_owner(
    permission, permission_model, resource_field, resource, verb="revoke"
):
    """A resource's last Owner-level grant can't be revoked or lowered, so it
    never ends up with nobody able to manage its sharing."""
    if permission.access_level != AccessLevel.OWNER:
        return

    owner_count = permission_model.objects.filter(
        access_level=AccessLevel.OWNER, **{resource_field: resource}
    ).count()
    if owner_count <= 1:
        raise ValidationError(
            {
                "detail": (
                    f"Cannot {verb} the {resource_field}'s last Owner. "
                    "Make someone else an Owner first."
                )
            }
        )
