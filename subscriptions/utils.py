from datetime import UTC, datetime


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
