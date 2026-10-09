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

    def solely_owned_by(self, user):
        """Rows where ``user`` holds the Owner level and no other active user
        does - the ones nobody could manage if ``user`` were deactivated."""
        permissions = self.model.permissions
        other_active_owners = permissions.rel.related_model.objects.filter(
            models.Q(**{permissions.field.name: models.OuterRef("pk")}),
            access_level=AccessLevel.OWNER,
            user__is_active=True,
        ).exclude(user=user)
        return self.filter(
            permissions__user=user, permissions__access_level=AccessLevel.OWNER
        ).exclude(models.Exists(other_active_owners))

    def visible_to(self, user):
        """The list/detail chokepoint: active rows in the user's organization
        they have any resolvable access to, annotated by
        :meth:`with_access_level`."""
        return (
            self.for_organization(user.organization)
            .with_access_level(user)
            .filter(user_access_level__isnull=False)
        )


def outside_trashed_projects(prefix=""):
    """Matches documents that are personal or whose project isn't in the trash.
    ``prefix`` reaches documents through a relation, e.g. ``"document__"``."""
    return models.Q(**{f"{prefix}project__isnull": True}) | models.Q(
        **{f"{prefix}project__is_active": True}
    )


class DocumentQuerySet(VisibilityScopedQuerySet):
    """Documents are scoped directly to their organization, not through the
    optional parent project."""

    def for_organization(self, organization):
        """Also hides documents filed under a project that's in the trash:
        they leave and return with their project. The documents' own
        ``is_active`` is untouched, so restoring the project brings back
        exactly the documents that were live, and the document trash still
        holds only documents deleted on their own."""
        return super().for_organization(organization).filter(outside_trashed_projects())

    def for_project(self, project):
        """Convenience narrowing to a single project's active documents."""
        return self.filter(project=project, is_active=True)


class DocumentVersionManager(models.Manager):
    def record(self, document, user):
        """Keeps ``document``'s title and content as they are now, as the
        version at its current revision, saved by ``user``. Called in the same
        transaction as the save that made that revision, so a document always
        has exactly one version per revision."""
        return self.create(
            document=document,
            revision=document.revision,
            title=document.title,
            content=document.content,
            created_by=user,
        )


class AttachmentQuerySet(models.QuerySet):
    def bytes_used_by(self, organization):
        """How much ``organization``'s attached files take up, in bytes -
        including those of documents in the trash, which are still stored."""
        return self.filter(document__organization=organization).aggregate(
            total=Coalesce(models.Sum("size"), 0)
        )["total"]
