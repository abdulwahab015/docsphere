from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase
from djstripe.models import Event
from djstripe.settings import djstripe_settings
from djstripe.signals import WEBHOOK_SIGNALS, webhook_processing_error

from clients import stripe as stripe_client
from organizations.factories import OrganizationFactory, StripeCustomerFactory


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
        )

        self.assertEqual(result.url, "https://checkout.stripe.com/x")
        mock_session_create.assert_called_once_with(
            customer="cus_test123",
            mode="subscription",
            line_items=[{"price": "price_test123", "quantity": 1}],
            success_url="https://example.com/success/",
            cancel_url="https://example.com/cancel/",
            api_key=djstripe_settings.STRIPE_SECRET_KEY,
        )


class UpdateCustomerEmailTests(SimpleTestCase):
    @patch("stripe.Customer.modify")
    def test_sets_the_customers_email(self, mock_customer_modify):
        stripe_client.update_customer_email(
            customer_id="cus_test123", email="billing@example.com"
        )

        mock_customer_modify.assert_called_once_with(
            "cus_test123",
            email="billing@example.com",
            api_key=djstripe_settings.STRIPE_SECRET_KEY,
        )

    @patch("stripe.Customer.modify")
    def test_clears_it_when_there_is_none(self, mock_customer_modify):
        stripe_client.update_customer_email(customer_id="cus_test123", email=None)

        self.assertEqual(mock_customer_modify.call_args.kwargs["email"], "")


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
