import logging

from django.dispatch import receiver
from djstripe.event_handlers import djstripe_receiver
from djstripe.signals import webhook_processing_error

logger = logging.getLogger(__name__)


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
