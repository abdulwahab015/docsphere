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


class DocumentManager(models.Manager):
    def for_organization(self, organization):
        """The tenant-isolation chokepoint for documents: every HTTP-layer
        queryset goes through here. Scoped to one organization (via the parent
        project) and to rows that haven't been soft-deleted."""
        return self.filter(project__organization=organization, is_active=True)

    def for_project(self, project):
        """Convenience narrowing of ``for_organization`` to a single project."""
        return self.filter(project=project, is_active=True)

    def inactive_for_organization(self, organization):
        """The restore endpoint's lookup set: scoped to one organization (via
        the parent project) and to already soft-deleted rows, the mirror image
        of ``for_organization``."""
        return self.filter(project__organization=organization, is_active=False)
