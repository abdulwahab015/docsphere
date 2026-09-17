from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from djstripe.models import Event
from djstripe.settings import djstripe_settings
from djstripe.signals import WEBHOOK_SIGNALS, webhook_processing_error

from clients import stripe as stripe_client
from organizations.factories import (
    OrganizationFactory,
    StripeCustomerFactory,
    StripePriceFactory,
    StripeSubscriptionFactory,
)


class GetOrCreateCustomerIdTests(TestCase):
    @patch("stripe.Customer.create")
    def test_returns_the_existing_customer_id(self, mock_customer_create):
        organization = OrganizationFactory()
        customer = StripeCustomerFactory(subscriber=organization)

        with self.assertNumQueries(1):
            customer_id = stripe_client.get_or_create_customer_id(organization)

        self.assertEqual(customer_id, customer.id)
        mock_customer_create.assert_not_called()

    @patch("stripe.Customer.create")
    def test_creates_a_customer_when_none_exists(self, mock_customer_create):
        mock_customer_create.return_value = {"id": "cus_test999", "livemode": False}
        organization = OrganizationFactory()

        customer_id = stripe_client.get_or_create_customer_id(organization)

        self.assertEqual(customer_id, "cus_test999")


class GetActiveSubscriptionTests(TestCase):
    def test_returns_the_active_subscription(self):
        organization = OrganizationFactory()
        subscription = StripeSubscriptionFactory(customer__subscriber=organization)

        with self.assertNumQueries(2):
            self.assertEqual(
                stripe_client.get_active_subscription(organization), subscription
            )

    def test_returns_none_without_a_customer(self):
        organization = OrganizationFactory()

        with self.assertNumQueries(1):
            self.assertIsNone(stripe_client.get_active_subscription(organization))

    def test_returns_none_when_customer_has_no_active_sub(self):
        organization = OrganizationFactory()
        StripeCustomerFactory(subscriber=organization)

        with self.assertNumQueries(2):
            self.assertIsNone(stripe_client.get_active_subscription(organization))


class IsActiveRecurringPriceTests(TestCase):
    def test_true_for_an_active_recurring_price(self):
        price = StripePriceFactory()

        with self.assertNumQueries(1):
            self.assertTrue(stripe_client.is_active_recurring_price(price.id))

    def test_false_for_an_inactive_price(self):
        price = StripePriceFactory(active=False)

        self.assertFalse(stripe_client.is_active_recurring_price(price.id))

    def test_false_for_an_unknown_price(self):
        self.assertFalse(stripe_client.is_active_recurring_price("price_doesnotexist"))


class GetExpiringSubscriptionsTests(TestCase):
    def test_returns_subscriptions_ending_within_the_window(self):
        now = timezone.now()
        subscription = StripeSubscriptionFactory(days_until_renewal=3)
        StripeSubscriptionFactory(days_until_renewal=30)

        with self.assertNumQueries(1):
            result = list(
                stripe_client.get_expiring_subscriptions(now, now + timedelta(days=7))
            )

        self.assertEqual(result, [subscription])

    def test_excludes_canceled_subscriptions(self):
        now = timezone.now()
        StripeSubscriptionFactory(days_until_renewal=3, status="canceled")

        result = list(
            stripe_client.get_expiring_subscriptions(now, now + timedelta(days=7))
        )

        self.assertEqual(result, [])


class CreateCheckoutSessionTests(SimpleTestCase):
    @patch("stripe.checkout.Session.create")
    def test_passes_through_the_expected_kwargs(self, mock_session_create):
        mock_session_create.return_value = MagicMock(
            url="https://checkout.stripe.com/x"
        )

        result = stripe_client.create_checkout_session(
            customer_id="cus_test123",
            price_id="price_test123",
            success_url="https://example.com/success/",
            cancel_url="https://example.com/cancel/",
            idempotency_key="checkout-1-price_test123-20260101",
        )

        self.assertEqual(result.url, "https://checkout.stripe.com/x")
        mock_session_create.assert_called_once_with(
            customer="cus_test123",
            mode="subscription",
            line_items=[{"price": "price_test123", "quantity": 1}],
            success_url="https://example.com/success/",
            cancel_url="https://example.com/cancel/",
            idempotency_key="checkout-1-price_test123-20260101",
            api_key=djstripe_settings.STRIPE_SECRET_KEY,
        )


class SubscriptionSignalTests(SimpleTestCase):
    def test_receiver_is_connected_for_created_and_updated_events(self):
        for event_name in (
            "customer.subscription.created",
            "customer.subscription.updated",
        ):
            with self.subTest(event_name=event_name):
                sync_receivers, _async_receivers = WEBHOOK_SIGNALS[
                    event_name
                ]._live_receivers(Event)
                self.assertIn(stripe_client.log_subscription_activated, sync_receivers)

    def test_logs_when_a_subscription_event_is_active(self):
        event = Event(
            id="evt_test_active",
            type="customer.subscription.updated",
            data={"object": {"id": "sub_test_active", "status": "active"}},
        )

        with self.assertLogs("subscriptions", level="INFO") as logs:
            stripe_client.log_subscription_activated(sender=Event, event=event)

        self.assertIn("Subscription activated via webhook", logs.output[0])

    def test_does_not_log_for_a_non_active_subscription_event(self):
        event = Event(
            id="evt_test_inactive",
            type="customer.subscription.updated",
            data={"object": {"id": "sub_test_inactive", "status": "canceled"}},
        )

        with self.assertNoLogs("subscriptions", level="INFO"):
            stripe_client.log_subscription_activated(sender=Event, event=event)

    def test_logs_a_webhook_processing_error(self):
        with self.assertLogs("subscriptions", level="ERROR") as logs:
            webhook_processing_error.send(
                sender=None,
                instance=None,
                api_key="sk_test_dummy",
                exception=ValueError("boom"),
                data="",
            )

        self.assertIn("Stripe webhook processing failed", logs.output[0])
