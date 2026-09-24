from django.db import models
from django.db.models.functions import Coalesce

from projects.choices import AccessLevel, Visibility


class VisibilityScopedQuerySet(models.QuerySet):
    """Shared by ``Project`` and ``Document``: both carry an ``organization``,
    a ``visibility`` and a ``permissions`` reverse relation to their
    per-user permission rows."""

    def for_organization(self, organization):
        """The tenant-isolation chokepoint: every HTTP-layer queryset goes
        through here. Scoped to one organization and to rows that haven't been
        soft-deleted."""
        return self.filter(organization=organization, is_active=True)

    def inactive_for_organization(self, organization):
        """The trash/restore lookup set: scoped to one organization and to
        already soft-deleted rows, the mirror image of ``for_organization``."""
        return self.filter(organization=organization, is_active=False)

    def with_access_level(self, user):
        """Annotates each row with ``user``'s effective level as
        ``user_access_level``, or ``None``.

        The level is the user's explicit permission row when one exists,
        whatever it grants; otherwise Viewer on a public row. Callers scope to
        the user's organization first, which is what makes the public default
        safe. The permission join is filtered to this one user, and a user has
        at most one row per resource, so no row is duplicated.
        """
        return self.annotate(
            user_permission=models.FilteredRelation(
                "permissions", condition=models.Q(permissions__user=user)
            )
        ).annotate(
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

    def visible_to(self, user):
        """The list/detail chokepoint: active rows in the user's organization
        they have any resolvable access to, annotated by
        :meth:`with_access_level`."""
        return (
            self.for_organization(user.organization)
            .with_access_level(user)
            .filter(user_access_level__isnull=False)
        )


class DocumentQuerySet(VisibilityScopedQuerySet):
    """Documents are scoped directly to their organization, not through the
    optional parent project."""

    def for_project(self, project):
        """Convenience narrowing to a single project's active documents."""
        return self.filter(project=project, is_active=True)
