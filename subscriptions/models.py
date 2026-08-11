# Subscriptions are managed by dj-stripe (djstripe.Customer / djstripe.Subscription).
# See subscriptions/services.py for subscription-state helpers.

from django.db import models
from djstripe.models import Customer

from subscriptions.services import get_active_subscription


class OrganizationSubscriptionMixin(models.Model):
    """Gives a subscriber-side model its dj-stripe Customer/Subscription lookups.

    Resolves via dj-stripe's own subscriber link (DJSTRIPE_SUBSCRIBER_MODEL)
    rather than a stored FK, since subscription state changes independently
    of the subscriber record.
    """

    class Meta:
        abstract = True

    @property
    def djstripe_customer(self):
        return Customer.objects.filter(subscriber=self).first()

    @property
    def active_subscription(self):
        return get_active_subscription(self)
