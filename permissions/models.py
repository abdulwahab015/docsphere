import uuid

from django.conf import settings
from django.db import models

from documents.models import Document, Project


class AccessLevel(models.TextChoices):
    """Shared role hierarchy: Owner > Editor > Viewer."""

    VIEWER = "VIEWER", "Viewer"
    EDITOR = "EDITOR", "Editor"
    OWNER = "OWNER", "Owner"


class ProjectPermission(models.Model):
    """Grants a user access to a project and, implicitly, its documents."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="permissions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_permissions",
    )
    access_level = models.CharField(max_length=10, choices=AccessLevel.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "user"], name="unique_project_permission_per_user"
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.project} ({self.access_level})"


class DocumentPermission(models.Model):
    """Grants/overrides a user's access to a single document."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="permissions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="document_permissions",
    )
    access_level = models.CharField(max_length=10, choices=AccessLevel.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document", "user"],
                name="unique_document_permission_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.document} ({self.access_level})"
