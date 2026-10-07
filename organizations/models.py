from functools import cached_property

from django.db import models
from djstripe.models import Customer

from core.models import TimeStampedModel
from subscriptions.utils import granting_access


class Organization(TimeStampedModel):
    """A tenant that owns users, projects, and a subscription."""

    name = models.CharField(max_length=100)
    billing_email = models.EmailField(blank=True, null=True, unique=True)
    last_expiry_reminder_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    @property
    def email(self):
        """Alias for dj-stripe, which requires its subscriber model
        (DJSTRIPE_SUBSCRIBER_MODEL = "organizations.Organization") to expose
        an `email` attribute."""
        return self.billing_email

    @cached_property
    def active_subscription(self):
        """The dj-stripe Subscription that gives the organization access, or
        None: an active one, or a past due one while Stripe retries a failed
        renewal payment."""
        customer = Customer.objects.filter(subscriber=self).first()
        if not customer:
            return None

        return granting_access(customer.subscriptions.all()).first()
