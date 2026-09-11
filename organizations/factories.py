from datetime import timedelta

import factory
from django.utils import timezone
from djstripe.models import Customer, Subscription, WebhookEndpoint

from organizations.models import Organization


class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Org {n}")


class StripeCustomerFactory(factory.django.DjangoModelFactory):
    """A dj-stripe Customer linked to an Organization. For local/dev/test only -
    real customers are created by Stripe and synced via the webhook."""

    class Meta:
        model = Customer

    id = factory.Sequence(lambda n: f"cus_test{n}")
    subscriber = factory.SubFactory(OrganizationFactory)
    stripe_data = factory.LazyAttribute(lambda o: {"id": o.id})


class StripeSubscriptionFactory(factory.django.DjangoModelFactory):
    """A dj-stripe Subscription. ``status`` (default ``"active"``) is written
    into ``stripe_data`` where dj-stripe's managers read it from - pass
    ``status="canceled"`` (or any non-active value) for an expired one."""

    class Meta:
        model = Subscription

    class Params:
        status = "active"
        days_until_renewal = 30

    id = factory.Sequence(lambda n: f"sub_test{n}")
    customer = factory.SubFactory(StripeCustomerFactory)
    stripe_data = factory.LazyAttribute(
        lambda o: {
            "id": o.id,
            "status": o.status,
            "current_period_end": int(
                (timezone.now() + timedelta(days=o.days_until_renewal)).timestamp()
            ),
        }
    )


class WebhookEndpointFactory(factory.django.DjangoModelFactory):
    """A dj-stripe WebhookEndpoint - the signing secret Stripe posts events
    against. For local/dev/test only; a real endpoint is created via the
    Stripe dashboard (or synced from it) and its secret stored here."""

    class Meta:
        model = WebhookEndpoint

    id = factory.Sequence(lambda n: f"we_test{n}")
    secret = factory.Sequence(lambda n: f"whsec_test{n}")
    enabled_events = factory.LazyFunction(lambda: ["*"])
    status = "enabled"
    url = factory.LazyAttribute(lambda o: f"https://example.com/stripe/webhook/{o.id}/")
    stripe_data = factory.LazyAttribute(lambda o: {"id": o.id})
