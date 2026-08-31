from typing import ClassVar

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models import TimeStampedModel
from users.choices import InvitationStatus, OrganizationRole
from users.managers import UserManager


class User(AbstractUser, TimeStampedModel):
    """A member of an organization, authenticated by email."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
    )

    email = models.EmailField(unique=True)
    org_role = models.CharField(
        max_length=10, choices=OrganizationRole.choices, default=OrganizationRole.MEMBER
    )

    username = None
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects = UserManager()

    def __str__(self):
        return self.email


class Invitation(TimeStampedModel):
    """A pending email invite for a user to join an organization."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invitations",
    )

    email = models.EmailField()
    token = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=10,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
    )
    accepted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.email} ({self.status})"
