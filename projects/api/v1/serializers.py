from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from projects.choices import AccessLevel
from projects.models import (
    Document,
    DocumentAccessRequest,
    DocumentPermission,
    Project,
    ProjectPermission,
)
from projects.permissions import resolve_access, resolve_project_access

User = get_user_model()


class AccessLevelModelSerializer(serializers.ModelSerializer):
    """Adds the requesting user's own read-only ``access_level`` on the
    resource, so a client knows which actions to offer without probing for
    403s - or ``null`` when they have none (an admin restoring a private
    project nobody granted them). Read from the ``user_access_level``
    annotation ``visible_to`` adds; a resource loaded any other way is
    resolved with one extra query instead."""

    access_level = serializers.SerializerMethodField()

    resolve_access_fn = None

    @extend_schema_field(
        serializers.ChoiceField(choices=AccessLevel.choices, allow_null=True)
    )
    def get_access_level(self, resource):
        level = getattr(resource, "user_access_level", None)
        if not level:
            level = self.resolve_access_fn(self.context["request"].user, resource)
        return level


class ProjectSerializer(AccessLevelModelSerializer):
    """``created_by`` and ``organization`` are always set server-side from the
    request and never accepted from the client. ``visibility`` is writable, but
    changing it on an existing project is Owner-only (enforced in the view)."""

    resolve_access_fn = staticmethod(resolve_project_access)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "visibility",
            "access_level",
            "created_by",
            "organization",
            "created",
            "modified",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "organization",
            "created",
            "modified",
        ]

    def validate_name(self, value):
        """Enforce per-organization name uniqueness here so a collision returns
        400 rather than surfacing as an IntegrityError. Soft-deleted projects
        still occupy the name (the DB constraint is unconditional), so they're
        included in the check."""
        organization = self.context["request"].user.organization
        clashes = Project.objects.filter(organization=organization, name=value)

        if self.instance:
            clashes = clashes.exclude(pk=self.instance.pk)

        if clashes.exists():
            raise serializers.ValidationError(
                "A project with this name already exists in your organization."
            )
        return value


class DocumentSerializer(AccessLevelModelSerializer):
    """``created_by``, ``organization`` and ``project`` are always set server-side
    in the view (the latter after explicit org-scoped validation, and may be left
    unset entirely for a personal document) and never accepted from the client
    through this serializer. ``visibility`` is writable, but changing it on an
    existing document is Owner-only (enforced in the view)."""

    resolve_access_fn = staticmethod(resolve_access)

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "content",
            "visibility",
            "access_level",
            "created_by",
            "organization",
            "project",
            "created",
            "modified",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "organization",
            "project",
            "created",
            "modified",
        ]


class ShareSerializer(serializers.Serializer):
    """Validates a grant/re-share request: a target user (by id) and the
    ``AccessLevel`` to give them. The target user must belong to the same
    organization as the resource being shared - checked against
    ``context["organization"]``, which the view supplies from the resource
    it already resolved (and therefore already org-scoped)."""

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    access_level = serializers.ChoiceField(choices=AccessLevel.choices)

    def validate_user(self, value):
        organization = self.context["organization"]
        if value.organization_id != organization.id:
            raise serializers.ValidationError(
                "This user does not belong to your organization."
            )
        return value


def _permission_serializer(model, resource_field):
    """Builds a read-only ModelSerializer exposing id, resource_field, user,
    and access_level - all read-only - for a permission model."""
    fields = ["id", resource_field, "user", "access_level"]
    meta = type(
        "Meta", (), {"model": model, "fields": fields, "read_only_fields": fields}
    )
    return type(
        f"{model.__name__}Serializer", (serializers.ModelSerializer,), {"Meta": meta}
    )


ProjectPermissionSerializer = _permission_serializer(ProjectPermission, "project")
DocumentPermissionSerializer = _permission_serializer(DocumentPermission, "document")


class DocumentAccessRequestSerializer(serializers.ModelSerializer):
    """Read-only - the view supplies ``document`` and ``requested_by`` from the
    URL and the requester, never from client-submitted data."""

    class Meta:
        model = DocumentAccessRequest
        fields = [
            "id",
            "document",
            "requested_by",
            "reviewed_by",
            "status",
            "created",
            "modified",
        ]
        read_only_fields = fields
