from datetime import UTC, datetime

from djstripe.models import Price


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


def active_recurring_prices():
    """The Prices an organization may subscribe to: active and recurring.
    Both the price list and checkout validation read through this, so
    anything listed is purchasable and vice versa."""
    return Price.objects.filter(active=True, stripe_data__type="recurring")
