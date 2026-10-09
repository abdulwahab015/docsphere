from functools import cached_property
from uuid import uuid4

from django.conf import settings
from django.db import models
from djstripe.models import Customer

from core.models import TimeStampedModel
from organizations.choices import ExportStatus
from organizations.constants import ORGANIZATION_PURGE_DELAY
from organizations.managers import OrganizationExportQuerySet, OrganizationQuerySet
from subscriptions.utils import granting_access


class Organization(TimeStampedModel):
    """A tenant that owns users, projects, and a subscription."""

    name = models.CharField(max_length=100)
    billing_email = models.EmailField(blank=True, null=True, unique=True)
    last_expiry_reminder_sent_at = models.DateTimeField(null=True, blank=True)
    # When an admin deleted the organization. From then on nobody in it can
    # use the app; its admins can restore it until ``purge_after``, when it
    # and everything in it are removed for good.
    deletion_requested_at = models.DateTimeField(null=True, blank=True)

    objects = OrganizationQuerySet.as_manager()

    def __str__(self):
        return self.name

    @property
    def email(self):
        """Alias for dj-stripe, which requires its subscriber model
        (DJSTRIPE_SUBSCRIBER_MODEL = "organizations.Organization") to expose
        an `email` attribute."""
        return self.billing_email

    @property
    def purge_after(self):
        """When a deleted organization is removed for good, or ``None``."""
        if not self.deletion_requested_at:
            return None
        return self.deletion_requested_at + ORGANIZATION_PURGE_DELAY

    @cached_property
    def active_subscription(self):
        """The dj-stripe Subscription that gives the organization access, or
        None: an active one, or a past due one while Stripe retries a failed
        renewal payment."""
        customer = Customer.objects.filter(subscriber=self).first()
        if not customer:
            return None

        return granting_access(customer.subscriptions.all()).first()


def export_path(export, _filename):
    """Where a built export is stored: under its organization, by a random
    name."""
    return f"exports/{export.organization_id}/{uuid4().hex}.zip"


class OrganizationExport(TimeStampedModel):
    """A .zip of an organization's data, built in the background for the
    admin who asked and downloadable through the API for a week from the
    link emailed to them. Holds only what that admin could open."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="exports"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="organization_exports",
    )

    status = models.CharField(
        max_length=10, choices=ExportStatus.choices, default=ExportStatus.BUILDING
    )
    # Empty until the background task has built it.
    file = models.FileField(upload_to=export_path, blank=True)

    objects = OrganizationExportQuerySet.as_manager()

    def __str__(self):
        return f"{self.organization} export ({self.created:%Y-%m-%d})"
