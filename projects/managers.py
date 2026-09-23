from django.db import models

from projects.choices import Visibility


class ProjectManager(models.Manager):
    def for_organization(self, organization):
        """The tenant-isolation chokepoint for projects: every HTTP-layer
        queryset goes through here. Scoped to one organization and to rows that
        haven't been soft-deleted."""
        return self.filter(organization=organization, is_active=True)

    def visible_to(self, user):
        """The list-endpoint chokepoint: projects the user has an explicit
        ProjectPermission on, plus every public project in their organization."""
        return (
            self.for_organization(user.organization)
            .filter(
                models.Q(permissions__user=user)
                | models.Q(visibility=Visibility.PUBLIC)
            )
            .distinct()
        )

    def inactive_for_organization(self, organization):
        """The restore endpoint's lookup set: scoped to one organization and to
        already soft-deleted rows, the mirror image of ``for_organization``."""
        return self.filter(organization=organization, is_active=False)


class DocumentManager(models.Manager):
    def for_organization(self, organization):
        """The tenant-isolation chokepoint for documents: every HTTP-layer
        queryset goes through here. Scoped directly to one organization (not
        through the optional parent project) and to rows that haven't been
        soft-deleted."""
        return self.filter(organization=organization, is_active=True)

    def visible_to(self, user):
        """The list-endpoint chokepoint: documents the user has an explicit
        DocumentPermission on, plus every public document in their organization."""
        return (
            self.for_organization(user.organization)
            .filter(
                models.Q(permissions__user=user)
                | models.Q(visibility=Visibility.PUBLIC)
            )
            .distinct()
        )

    def for_project(self, project):
        """Convenience narrowing of ``for_organization`` to a single project."""
        return self.filter(project=project, is_active=True)

    def inactive_for_organization(self, organization):
        """The restore endpoint's lookup set: scoped to one organization and to
        already soft-deleted rows, the mirror image of ``for_organization``."""
        return self.filter(organization=organization, is_active=False)
