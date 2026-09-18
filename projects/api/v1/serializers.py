from django.contrib.auth import get_user_model
from rest_framework import serializers

from projects.choices import AccessLevel
from projects.models import Document, DocumentPermission, Project, ProjectPermission

User = get_user_model()


class ProjectSerializer(serializers.ModelSerializer):
    """``created_by`` and ``organization`` are always set server-side from the
    request and never accepted from the client."""

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
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


class DocumentSerializer(serializers.ModelSerializer):
    """``created_by`` and ``project`` are always set server-side in the view
    (the latter after explicit org-scoped validation) and never accepted from
    the client through this serializer."""

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "content",
            "created_by",
            "project",
            "created",
            "modified",
        ]
        read_only_fields = [
            "id",
            "created_by",
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
