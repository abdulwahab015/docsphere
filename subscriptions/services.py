from django.conf import settings
from djstripe.models import Customer

from clients import stripe as stripe_client
from subscriptions.exceptions import PaymentProviderUnavailable


def create_checkout_session(organization, price_id):
    """Creates a Stripe Checkout Session for the organization's subscription
    purchase and returns its hosted URL.

    Only creates the Checkout Session itself — no local Subscription state is
    written here. That happens exclusively via the Stripe webhook once the
    customer actually completes payment.
    """
    customer_id = stripe_client.get_or_create_customer_id(organization)

    session = stripe_client.create_checkout_session(
        customer_id=customer_id,
        price_id=price_id,
        success_url=f"{settings.FRONTEND_URL}/billing/success/",
        cancel_url=f"{settings.FRONTEND_URL}/billing/cancel/",
    )

    return session.url


def create_billing_portal_session(organization):
    """Creates a Stripe Customer Portal session for the organization and
    returns its hosted URL, or ``None`` if the organization has never been
    through checkout - with no Stripe customer, there's nothing to manage.

    Deliberately doesn't create a customer the way checkout does: the portal
    only makes sense for an organization that already has billing history.
    """
    customer = Customer.objects.filter(subscriber=organization).first()
    if not customer:
        return None

    session = stripe_client.create_billing_portal_session(
        customer_id=customer.id,
        return_url=f"{settings.FRONTEND_URL}/billing/",
    )
    return session.url


def sync_billing_email(organization):
    """Gives the organization's Stripe customer its current billing email, so
    receipts and invoices go there. An organization that has never been
    through checkout has no customer yet - checkout creates one with the
    email it has then. Raises ``PaymentProviderUnavailable`` if Stripe can't
    be updated, so the caller can keep the two from disagreeing."""
    customer = Customer.objects.filter(subscriber=organization).first()
    if not customer:
        return

    try:
        stripe_client.update_customer_email(
            customer_id=customer.id, email=organization.billing_email
        )
    except stripe_client.StripeError as error:
        raise PaymentProviderUnavailable() from error
