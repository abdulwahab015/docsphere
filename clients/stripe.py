import logging

import stripe
from django.dispatch import receiver
from djstripe.event_handlers import djstripe_receiver
from djstripe.models import Customer, Price, Subscription
from djstripe.settings import djstripe_settings
from djstripe.signals import webhook_processing_error

logger = logging.getLogger("subscriptions")


def get_or_create_customer_id(subscriber):
    """Returns the Stripe customer id for subscriber, creating one via the
    Stripe API if none exists yet."""
    customer, _ = Customer.get_or_create(subscriber=subscriber)
    return customer.id


def get_active_subscription(subscriber):
    """Returns subscriber's current active dj-stripe Subscription, or None."""
    customer = Customer.objects.filter(subscriber=subscriber).first()
    if not customer:
        return None

    return customer.subscriptions.active().first()


def is_active_recurring_price(price_id):
    """True if price_id is a currently active, recurring dj-stripe Price."""
    return Price.objects.filter(
        id=price_id, active=True, stripe_data__type="recurring"
    ).exists()


def get_expiring_subscriptions(window_start, window_end):
    """Returns active dj-stripe Subscriptions whose current period ends within
    [window_start, window_end], with their Customer preloaded."""
    return (
        Subscription.objects.active()
        .filter(
            stripe_data__current_period_end__gte=int(window_start.timestamp()),
            stripe_data__current_period_end__lte=int(window_end.timestamp()),
        )
        .select_related("customer")
    )


def create_checkout_session(
    *, customer_id, price_id, success_url, cancel_url, idempotency_key
):
    """Thin wrapper around the Stripe SDK's Checkout Session creation call."""
    return stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        idempotency_key=idempotency_key,
        api_key=djstripe_settings.STRIPE_SECRET_KEY,
    )


@receiver(webhook_processing_error)
def log_webhook_processing_error(sender, instance, api_key, exception, data, **kwargs):
    logger.error(
        "Stripe webhook processing failed: %s",
        exception,
        extra={"webhook_event_trigger_id": getattr(instance, "id", None)},
    )


@djstripe_receiver(["customer.subscription.created", "customer.subscription.updated"])
def log_subscription_activated(sender, event, **kwargs):
    """Logs subscription activation for visibility only.

    Organization.active_subscription reads live from
    customer.subscriptions.active() on every access, so no local state needs
    to be created or updated here.
    """
    subscription_object = event.data.get("object", {})
    if subscription_object.get("status") != "active":
        return

    logger.info(
        "Subscription activated via webhook",
        extra={"subscription_id": subscription_object.get("id")},
    )
