from functools import cached_property

from django.db import models
from djstripe.models import Customer

from core.models import TimeStampedModel


class Organization(TimeStampedModel):
    """A tenant that owns users, projects, and a subscription."""

    name = models.CharField(max_length=100)
    billing_email = models.EmailField(blank=True, null=True, unique=True)

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
        """Returns the org's current active dj-stripe Subscription, or None."""

        customer = Customer.objects.filter(subscriber=self).first()
        if customer is None:
            return None

        return customer.subscriptions.active().first()
