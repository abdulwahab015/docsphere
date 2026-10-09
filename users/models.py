from typing import ClassVar

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel
from users.choices import InvitationStatus, OrganizationRole
from users.constants import MAX_NAME_LENGTH
from users.fields import EmailField
from users.managers import InvitationManager, UserManager


class User(AbstractUser, TimeStampedModel):
    """A member of an organization, authenticated by email."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
    )

    email = EmailField(unique=True)
    # How the person is named to everyone else, as they typed it - one field,
    # since not every name splits into a first and a last. Empty until given;
    # the email stands in for it until then.
    name = models.CharField(max_length=MAX_NAME_LENGTH, blank=True)
    org_role = models.CharField(
        max_length=10, choices=OrganizationRole.choices, default=OrganizationRole.MEMBER
    )
    # When the person proved they own ``email`` by following a link sent to
    # it; empty for a signup that hasn't yet. An invitation's link proves it
    # too, so invited members start verified.
    email_verified_at = models.DateTimeField(null=True, blank=True)
    # When the person deleted their own account. It's kept, inactive and
    # without their name, email or password, so what they wrote keeps an
    # author; unlike a deactivated account it can never be reactivated.
    deleted_at = models.DateTimeField(null=True, blank=True)

    username = None
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects = UserManager()

    def __str__(self):
        return self.email

    @property
    def email_verified(self):
        return bool(self.email_verified_at)

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

    @property
    def name_and_email(self):
        """How an email to someone else refers to this person: their name with
        their address, or just the address while they haven't given a name."""
        return f"{self.name} ({self.email})" if self.name else self.email


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

    email = EmailField()
    token = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=10,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
    )
    sent_at = models.DateTimeField(default=timezone.now)
    accepted_at = models.DateTimeField(null=True, blank=True)

    objects = InvitationManager()

    def __str__(self):
        return f"{self.email} ({self.status})"

    @property
    def is_expired(self):
        """Still stored as pending, but sent longer ago than
        ``INVITATION_EXPIRY``, so its link no longer works. Expiry is worked
        out on read and never written back; a resend restarts the window."""
        return (
            self.status == InvitationStatus.PENDING
            and timezone.now() - self.sent_at > settings.INVITATION_EXPIRY
        )

    @property
    def current_status(self):
        """``status`` as the invitee would find it: ``EXPIRED`` once a
        pending link has run out."""
        return InvitationStatus.EXPIRED if self.is_expired else self.status
