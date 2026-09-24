from django.db import models
from django.db.models.functions import Coalesce

from projects.choices import AccessLevel, Visibility


class VisibilityScopedManager(models.Manager):
    """Shared by ``Project`` and ``Document``: both carry an ``organization``,
    a ``visibility`` and a ``permissions`` reverse relation to their
    per-user permission rows."""

    def for_organization(self, organization):
        """The tenant-isolation chokepoint: every HTTP-layer queryset goes
        through here. Scoped to one organization and to rows that haven't been
        soft-deleted."""
        return self.filter(organization=organization, is_active=True)

    def visible_to(self, user):
        """The list/detail chokepoint: rows ``user`` has any resolvable access
        to, each annotated with that level as ``user_access_level``.

        The level is the user's explicit permission row when one exists,
        whatever it grants; otherwise Viewer on a public row. Rows resolving to
        neither are excluded. The organization check a public row needs is
        already implied by ``for_organization``. The permission join is
        filtered to this one user, and a user has at most one row per resource,
        so no row is duplicated.
        """
        return (
            self.for_organization(user.organization)
            .annotate(
                user_permission=models.FilteredRelation(
                    "permissions", condition=models.Q(permissions__user=user)
                )
            )
            .annotate(
                user_access_level=Coalesce(
                    "user_permission__access_level",
                    models.Case(
                        models.When(
                            visibility=Visibility.PUBLIC,
                            then=models.Value(AccessLevel.VIEWER),
                        ),
                        output_field=models.CharField(),
                    ),
                )
            )
            .filter(user_access_level__isnull=False)
        )

    def inactive_for_organization(self, organization):
        """The restore endpoint's lookup set: scoped to one organization and to
        already soft-deleted rows, the mirror image of ``for_organization``."""
        return self.filter(organization=organization, is_active=False)


class DocumentManager(VisibilityScopedManager):
    """Documents are scoped directly to their organization, not through the
    optional parent project."""

    def for_project(self, project):
        """Convenience narrowing of ``for_organization`` to a single project."""
        return self.filter(project=project, is_active=True)
