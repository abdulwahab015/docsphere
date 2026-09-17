from django.conf import settings
from django.utils import timezone

from clients import stripe as stripe_client


def create_checkout_session(organization, price_id):
    """Creates a Stripe Checkout Session for the organization's subscription
    purchase and returns its hosted URL.

    Only creates the Checkout Session itself — no local Subscription state is
    written here. That happens exclusively via the Stripe webhook once the
    customer actually completes payment.
    """
    customer_id = stripe_client.get_or_create_customer_id(organization)

    idempotency_key = f"checkout-{organization.pk}-{price_id}-{timezone.now():%Y%m%d}"

    session = stripe_client.create_checkout_session(
        customer_id=customer_id,
        price_id=price_id,
        success_url=f"{settings.FRONTEND_URL}/billing/success/",
        cancel_url=f"{settings.FRONTEND_URL}/billing/cancel/",
        idempotency_key=idempotency_key,
    )

    return session.url
