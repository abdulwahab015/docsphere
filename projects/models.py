from django.conf import settings
from django.db import models
from django_extensions.db.models import TimeStampedModel

from core.models import ActiveModel
from projects.choices import AccessLevel


class Project(TimeStampedModel, ActiveModel):
    """A collection of documents scoped to a single organization."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="projects"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_projects",
    )

    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="unique_organization_project_name",
                violation_error_message="A project with this name already exists in your organization.",
            )
        ]

    def __str__(self):
        return self.name


class Document(TimeStampedModel, ActiveModel):
    """A text note/document that belongs to a project."""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="documents"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_documents",
    )

    title = models.CharField(max_length=100, db_index=True)
    content = models.TextField(blank=True)

    def __str__(self):
        return self.title


class ProjectPermission(models.Model):
    """Grants a user access to a project and, implicitly, its documents."""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="permissions"
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
                fields=["project", "user"],
                name="unique_project_user_permission",
                violation_error_message="This user already has a permission assigned for this project.",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.project} ({self.access_level})"


class DocumentPermission(models.Model):
    """Grants/overrides a user's access to a single document."""

    document = models.ForeignKey(
        "projects.Document", on_delete=models.CASCADE, related_name="permissions"
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
                name="unique_document_user_permission",
                violation_error_message="This user already has a permission assigned for this document.",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.document} ({self.access_level})"
