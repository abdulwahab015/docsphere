from rest_framework.exceptions import ValidationError

from projects.choices import AccessLevel


def ensure_not_last_owner(
    permission, permission_model, resource_field, resource, verb="revoke"
):
    """A resource's last active Owner can't be revoked or lowered, so it never
    ends up with nobody able to manage its sharing. A deactivated Owner can't
    manage anything, so they don't count as one - and removing them is allowed
    as long as an active Owner remains."""
    if permission.access_level != AccessLevel.OWNER:
        return

    other_active_owners = permission_model.objects.filter(
        access_level=AccessLevel.OWNER,
        user__is_active=True,
        **{resource_field: resource},
    ).exclude(pk=permission.pk)
    if not other_active_owners.exists():
        raise ValidationError(
            {
                "detail": (
                    f"Cannot {verb} the {resource_field}'s last Owner. "
                    "Make someone else an Owner first."
                )
            }
        )
