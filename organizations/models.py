from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models import TimeStampedModel
from organizations.choices import InvitationStatus, OrgRole
from subscriptions.models import OrganizationSubscriptionMixin


class Organization(TimeStampedModel, OrganizationSubscriptionMixin):
    """A tenant that owns users, projects, and a subscription."""

    name = models.CharField(max_length=100)
    billing_email = models.EmailField(blank=True)

    def __str__(self):
        return self.name

    @property
    def email(self):
        """Alias for dj-stripe, which requires its subscriber model
        (DJSTRIPE_SUBSCRIBER_MODEL = "organizations.Organization") to expose
        an `email` attribute."""
        return self.billing_email


class User(AbstractUser):
    """A member of an organization, authenticated by email."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="users"
    )
    email = models.EmailField(unique=True)
    org_role = models.CharField(
        max_length=10, choices=OrgRole.choices, default=OrgRole.MEMBER
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["username"]

    def __str__(self):
        return self.email


class Invitation(TimeStampedModel):
    """A pending email invite for a user to join an organization."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invitations"
    )
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="sent_invitations"
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
