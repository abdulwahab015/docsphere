import stripe
from django.conf import settings
from django.utils import timezone
from djstripe.models import Customer
from djstripe.settings import djstripe_settings


def create_checkout_session(organization, price_id):
    """Creates a Stripe Checkout Session for the organization's subscription
    purchase and returns its hosted URL.

    Only creates the Checkout Session itself — no local Subscription state is
    written here. That happens exclusively via the Stripe webhook once the
    customer actually completes payment.
    """
    customer, _ = Customer.get_or_create(subscriber=organization)

    idempotency_key = f"checkout-{organization.pk}-{price_id}-{timezone.now():%Y%m%d}"

    session = stripe.checkout.Session.create(
        customer=customer.id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.FRONTEND_URL}/billing/success/",
        cancel_url=f"{settings.FRONTEND_URL}/billing/cancel/",
        idempotency_key=idempotency_key,
        api_key=djstripe_settings.STRIPE_SECRET_KEY,
    )

    return session.url
