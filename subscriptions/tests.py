from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from djstripe.models import Event
from djstripe.signals import WEBHOOK_SIGNALS, webhook_processing_error
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from organizations.factories import OrganizationFactory, StripeSubscriptionFactory
from subscriptions.signals import log_subscription_activated
from subscriptions.tasks import send_expiry_reminders_task
from users.factories import AdminUserFactory, UserFactory


class CheckoutSessionCreateAPIViewTests(APITestCase):
    def setUp(self):
        self.url = reverse("subscriptions_checkout")

    @patch("stripe.checkout.Session.create")
    @patch("stripe.Customer.create")
    def test_org_admin_with_billing_email_gets_checkout_url(
        self, mock_customer_create, mock_session_create
    ):
        mock_customer_create.return_value = {"id": "cus_test123", "livemode": False}
        mock_session_create.return_value = MagicMock(
            url="https://checkout.stripe.com/session_test123"
        )
        organization = OrganizationFactory(billing_email="billing@example.com")
        admin = AdminUserFactory(organization=organization)
        self.client.force_authenticate(admin)

        with self.assertNumQueries(9):
            response = self.client.post(self.url, {"plan": "MONTHLY"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["checkout_url"], "https://checkout.stripe.com/session_test123"
        )
        mock_session_create.assert_called_once()
        self.assertEqual(
            mock_session_create.call_args.kwargs["customer"], "cus_test123"
        )
        self.assertEqual(mock_session_create.call_args.kwargs["mode"], "subscription")
        self.assertIn("idempotency_key", mock_session_create.call_args.kwargs)

    @patch("stripe.checkout.Session.create")
    @patch("stripe.Customer.create")
    def test_checkout_is_rate_limited(self, mock_customer_create, mock_session_create):
        mock_customer_create.return_value = {"id": "cus_test123", "livemode": False}
        mock_session_create.return_value = MagicMock(
            url="https://checkout.stripe.com/session_test123"
        )
        organization = OrganizationFactory(billing_email="billing@example.com")
        admin = AdminUserFactory(organization=organization)
        self.client.force_authenticate(admin)

        cache.clear()
        with patch.object(
            ScopedRateThrottle, "THROTTLE_RATES", {"billing_checkout": "1/min"}
        ):
            with self.assertNumQueries(9):
                first = self.client.post(self.url, {"plan": "MONTHLY"})
            self.assertEqual(first.status_code, status.HTTP_200_OK)

            with self.assertNumQueries(0):
                second = self.client.post(self.url, {"plan": "MONTHLY"})
            self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_org_admin_without_billing_email_gets_400(self):
        organization = OrganizationFactory(billing_email=None)
        admin = AdminUserFactory(organization=organization)
        self.client.force_authenticate(admin)

        with self.assertNumQueries(0):
            response = self.client.post(self.url, {"plan": "MONTHLY"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_admin_gets_403(self):
        organization = OrganizationFactory(billing_email="billing@example.com")
        member = UserFactory(organization=organization)
        self.client.force_authenticate(member)

        with self.assertNumQueries(0):
            response = self.client.post(self.url, {"plan": "MONTHLY"})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_plan_gets_400(self):
        organization = OrganizationFactory(billing_email="billing@example.com")
        admin = AdminUserFactory(organization=organization)
        self.client.force_authenticate(admin)

        with self.assertNumQueries(0):
            response = self.client.post(self.url, {"plan": "WEEKLY"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


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
                self.assertIn(log_subscription_activated, sync_receivers)

    def test_logs_when_a_subscription_event_is_active(self):
        event = Event(
            id="evt_test_active",
            type="customer.subscription.updated",
            data={"object": {"id": "sub_test_active", "status": "active"}},
        )

        with self.assertLogs("subscriptions", level="INFO") as logs:
            log_subscription_activated(sender=Event, event=event)

        self.assertIn("Subscription activated via webhook", logs.output[0])

    def test_does_not_log_for_a_non_active_subscription_event(self):
        event = Event(
            id="evt_test_inactive",
            type="customer.subscription.updated",
            data={"object": {"id": "sub_test_inactive", "status": "canceled"}},
        )

        with self.assertNoLogs("subscriptions", level="INFO"):
            log_subscription_activated(sender=Event, event=event)

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


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    SUBSCRIPTION_EXPIRY_REMINDER_DAYS=7,
)
class ExpiryReminderTaskTests(TestCase):
    @patch("core.email.send_mail")
    def test_org_within_the_window_and_not_yet_reminded_gets_reminded(
        self, mock_send_mail
    ):
        organization = OrganizationFactory(billing_email="billing@example.com")
        StripeSubscriptionFactory(
            customer__subscriber=organization, days_until_renewal=3
        )

        with self.assertNumQueries(6):
            send_expiry_reminders_task()

        mock_send_mail.assert_called_once()
        organization.refresh_from_db()
        self.assertIsNotNone(organization.last_expiry_reminder_sent_at)

    @patch("core.email.send_mail")
    def test_already_reminded_org_is_not_reminded_again(self, mock_send_mail):
        organization = OrganizationFactory(
            billing_email="billing@example.com",
            last_expiry_reminder_sent_at=timezone.now(),
        )
        StripeSubscriptionFactory(
            customer__subscriber=organization, days_until_renewal=3
        )

        with self.assertNumQueries(2):
            send_expiry_reminders_task()

        mock_send_mail.assert_not_called()

    @patch("core.email.send_mail")
    def test_org_outside_the_window_is_skipped(self, mock_send_mail):
        organization = OrganizationFactory(billing_email="billing@example.com")
        StripeSubscriptionFactory(
            customer__subscriber=organization, days_until_renewal=30
        )

        with self.assertNumQueries(1):
            send_expiry_reminders_task()

        mock_send_mail.assert_not_called()

    @patch("core.email.send_mail")
    def test_org_without_an_active_subscription_is_skipped(self, mock_send_mail):
        OrganizationFactory(billing_email="billing@example.com")

        with self.assertNumQueries(1):
            send_expiry_reminders_task()

        mock_send_mail.assert_not_called()
