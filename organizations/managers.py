from django.db import models
from django.utils import timezone

from organizations.choices import ExportStatus
from organizations.constants import EXPORT_BUILD_TIMEOUT, ORGANIZATION_PURGE_DELAY


class OrganizationQuerySet(models.QuerySet):
    def due_for_purge(self):
        """Organizations deleted longer ago than they can be restored."""
        return self.filter(
            deletion_requested_at__lt=timezone.now() - ORGANIZATION_PURGE_DELAY
        )


class OrganizationExportQuerySet(models.QuerySet):
    def building(self):
        """Exports still being built - not counting one that has been at it
        longer than any build takes, whose worker must have died."""
        return self.filter(
            status=ExportStatus.BUILDING,
            created__gte=timezone.now() - EXPORT_BUILD_TIMEOUT,
        )

    def ready(self):
        return self.filter(status=ExportStatus.READY)
