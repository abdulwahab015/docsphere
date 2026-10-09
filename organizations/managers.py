from django.db import models
from django.utils import timezone

from organizations.constants import ORGANIZATION_PURGE_DELAY


class OrganizationQuerySet(models.QuerySet):
    def due_for_purge(self):
        """Organizations deleted longer ago than they can be restored."""
        return self.filter(
            deletion_requested_at__lt=timezone.now() - ORGANIZATION_PURGE_DELAY
        )
