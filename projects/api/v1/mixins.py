from django.db import transaction

from audit.choices import AuditVerb
from audit.models import AuditEvent


class SoftDeleteMixin:
    """Flips ``is_active`` instead of hard-deleting, so the row drops out of
    every ``for_organization`` queryset, and records who did it."""

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_active = False
            instance.save(update_fields=["is_active"])
            # The event's project/document field shares the model's name.
            AuditEvent.objects.record(
                self.request.user,
                AuditVerb.DELETED,
                **{instance._meta.model_name: instance},
            )
