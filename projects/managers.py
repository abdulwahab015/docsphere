from django.db import models


class ProjectManager(models.Manager):
    def for_organization(self, organization):
        """The tenant-isolation chokepoint for projects: every HTTP-layer
        queryset goes through here. Scoped to one organization and to rows that
        haven't been soft-deleted."""
        return self.filter(organization=organization, is_active=True)

    def inactive_for_organization(self, organization):
        """The restore endpoint's lookup set: scoped to one organization and to
        already soft-deleted rows, the mirror image of ``for_organization``."""
        return self.filter(organization=organization, is_active=False)
