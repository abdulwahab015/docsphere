from datetime import UTC, datetime

from django.conf import settings
from djstripe.models import Price

from subscriptions.choices import SubscriptionStatus

# Past due: a renewal payment failed and Stripe is retrying the card. The
# organization keeps its access until Stripe gives up (unpaid or canceled).
ACCESS_GRANTING_STATUSES = (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE)


def get_period_end(subscription):
    """Current billing period end of a dj-stripe Subscription, or None.

    Current Stripe API versions report it on the subscription item; it is no
    longer on the subscription object itself, and dj-stripe's own
    ``current_period_end`` property only reads the old location.
    """
    items = subscription.stripe_data.get("items", {}).get("data") or [{}]
    timestamp = items[0].get("current_period_end")
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC)


def granting_access(subscriptions):
    """Narrows a queryset of dj-stripe Subscriptions to those that give their
    organization access."""
    return subscriptions.filter(stripe_data__status__in=ACCESS_GRANTING_STATUSES)


def is_past_due(subscription):
    """Whether a renewal payment failed and Stripe is still retrying it."""
    return subscription.stripe_data.get("status") == SubscriptionStatus.PAST_DUE


def cancels_at_period_end(subscription):
    """Whether a dj-stripe Subscription has been cancelled and ends when its
    current billing period does, rather than renewing."""
    return bool(subscription.stripe_data.get("cancel_at_period_end"))


def active_recurring_prices():
    """The Prices an organization may subscribe to: active, recurring, and of
    the configured DocSphere product. Both the price list and checkout
    validation read through this, so anything listed is purchasable and vice
    versa."""
    return Price.objects.filter(
        product_id=settings.STRIPE_PRODUCT_ID,
        active=True,
        stripe_data__type="recurring",
    )
