from django.conf import settings
from django.db import models

from core.models import TimeStampedModel
from projects.choices import AccessLevel, AccessRequestStatus, Visibility
from projects.managers import DocumentManager, VisibilityScopedManager


class Project(TimeStampedModel):
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
    description = models.TextField(null=True, blank=True)
    visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.PRIVATE
    )

    objects = VisibilityScopedManager()

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


class Document(TimeStampedModel):
    """A text note/document, optionally organized under a project. A document with no
    project is a personal document, still scoped to its creator's organization."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="documents"
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="documents",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_documents",
    )

    title = models.CharField(max_length=100, db_index=True)
    content = models.TextField(null=True, blank=True)
    visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.PRIVATE
    )

    objects = DocumentManager()

    def __str__(self):
        return self.title


class ProjectPermission(models.Model):
    """Grants a user access to a project. No longer implies anything about the
    project's documents - it only governs the project resource itself and, via
    ``Action.WRITE``, who may create documents inside it."""

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
    """Grants a user access to a single document."""

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


class DocumentAccessRequest(TimeStampedModel):
    """A Viewer's request to be upgraded to Editor on a document they can see (typically
    because it's public). Only the document's Owner(s) may approve or deny it."""

    document = models.ForeignKey(
        "projects.Document", on_delete=models.CASCADE, related_name="access_requests"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="document_access_requests",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_document_access_requests",
    )

    status = models.CharField(
        max_length=10,
        choices=AccessRequestStatus.choices,
        default=AccessRequestStatus.PENDING,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document", "requested_by"],
                condition=models.Q(status=AccessRequestStatus.PENDING),
                name="unique_pending_access_request_per_user_per_document",
                violation_error_message="You already have a pending request for this document.",
            )
        ]

    def __str__(self):
        return f"{self.requested_by} -> {self.document} ({self.status})"
