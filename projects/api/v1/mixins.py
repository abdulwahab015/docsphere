class SoftDeleteMixin:
    """Flips ``is_active`` instead of hard-deleting, so the row drops out of
    every ``for_organization`` queryset."""

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])
