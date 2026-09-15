from rest_framework import serializers

from projects.models import Document, Project


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
