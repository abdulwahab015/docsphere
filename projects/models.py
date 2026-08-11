from django.conf import settings
from django.db import models

from core.models import TimeStampedModel
from projects.choices import AccessLevel


class Project(TimeStampedModel):
    """A collection of documents scoped to a single organization."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="projects"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_projects",
    )
    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ("organization", "name")

    def __str__(self):
        return self.name


class Document(TimeStampedModel):
    """A text note/document that belongs to a project."""

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="documents"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_documents",
    )
    title = models.CharField(max_length=100, db_index=True)
    content = models.TextField(blank=True)

    def __str__(self):
        return self.title


class ProjectPermission(models.Model):
    """Grants a user access to a project and, implicitly, its documents."""

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
        unique_together = ("project", "user")

    def __str__(self):
        return f"{self.user} - {self.project} ({self.access_level})"


class DocumentPermission(models.Model):
    """Grants/overrides a user's access to a single document."""

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
        unique_together = ("document", "user")

    def __str__(self):
        return f"{self.user} - {self.document} ({self.access_level})"
