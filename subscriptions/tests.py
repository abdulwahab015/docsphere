from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from organizations.factories import (
    OrganizationFactory,
    StripeCustomerFactory,
    StripePriceFactory,
    StripeSubscriptionFactory,
)
from subscriptions.tasks import (
    send_expiry_reminder_email_task,
    send_expiry_reminders_task,
)
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
        price = StripePriceFactory()
        self.client.force_authenticate(admin)

        with self.assertNumQueries(10):
            response = self.client.post(self.url, {"price_id": price.id})

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
        price = StripePriceFactory()
        self.client.force_authenticate(admin)

        cache.clear()
        with patch.object(
            ScopedRateThrottle, "THROTTLE_RATES", {"billing_checkout": "1/min"}
        ):
            with self.assertNumQueries(10):
                first = self.client.post(self.url, {"price_id": price.id})
            self.assertEqual(first.status_code, status.HTTP_200_OK)

            with self.assertNumQueries(0):
                second = self.client.post(self.url, {"price_id": price.id})
            self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_org_admin_without_billing_email_gets_400(self):
        organization = OrganizationFactory(billing_email=None)
        admin = AdminUserFactory(organization=organization)
        price = StripePriceFactory()
        self.client.force_authenticate(admin)

        with self.assertNumQueries(1):
            response = self.client.post(self.url, {"price_id": price.id})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_admin_gets_403(self):
        organization = OrganizationFactory(billing_email="billing@example.com")
        member = UserFactory(organization=organization)
        self.client.force_authenticate(member)

        with self.assertNumQueries(0):
            response = self.client.post(self.url, {"price_id": "price_irrelevant"})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_price_gets_400(self):
        organization = OrganizationFactory(billing_email="billing@example.com")
        admin = AdminUserFactory(organization=organization)
        self.client.force_authenticate(admin)

        with self.assertNumQueries(1):
            response = self.client.post(self.url, {"price_id": "price_doesnotexist"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_price_gets_400(self):
        organization = OrganizationFactory(billing_email="billing@example.com")
        admin = AdminUserFactory(organization=organization)
        price = StripePriceFactory(active=False)
        self.client.force_authenticate(admin)

        with self.assertNumQueries(1):
            response = self.client.post(self.url, {"price_id": price.id})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


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

        with self.assertNumQueries(5):
            send_expiry_reminders_task()

        mock_send_mail.assert_called_once()
        _, kwargs = mock_send_mail.call_args
        expected_date = (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        self.assertIn(expected_date, kwargs["message"])
        self.assertEqual(kwargs["recipient_list"], ["billing@example.com"])
        organization.refresh_from_db()
        self.assertIsNotNone(organization.last_expiry_reminder_sent_at)

    @patch("core.email.send_mail")
    def test_org_reminded_in_a_previous_period_is_reminded_again(self, mock_send_mail):
        organization = OrganizationFactory(
            billing_email="billing@example.com",
            last_expiry_reminder_sent_at=timezone.now() - timedelta(days=28),
        )
        StripeSubscriptionFactory(
            customer__subscriber=organization, days_until_renewal=3
        )

        send_expiry_reminders_task()

        mock_send_mail.assert_called_once()

    @patch("core.email.send_mail")
    def test_org_is_reminded_once_even_with_several_active_subscriptions(
        self, mock_send_mail
    ):
        organization = OrganizationFactory(billing_email="billing@example.com")
        customer = StripeCustomerFactory(subscriber=organization)
        StripeSubscriptionFactory(customer=customer, days_until_renewal=3)
        StripeSubscriptionFactory(customer=customer, days_until_renewal=2)

        send_expiry_reminders_task()

        mock_send_mail.assert_called_once()

    @patch("core.email.send_mail")
    def test_reminder_email_is_skipped_if_the_subscription_lapsed_meanwhile(
        self, mock_send_mail
    ):
        organization = OrganizationFactory(billing_email="billing@example.com")
        StripeSubscriptionFactory(
            customer__subscriber=organization, status="canceled", days_until_renewal=3
        )

        send_expiry_reminder_email_task(organization.pk)

        mock_send_mail.assert_not_called()
        organization.refresh_from_db()
        self.assertIsNone(organization.last_expiry_reminder_sent_at)

    @patch("core.email.send_mail")
    def test_already_reminded_org_is_not_reminded_again(self, mock_send_mail):
        organization = OrganizationFactory(
            billing_email="billing@example.com",
            last_expiry_reminder_sent_at=timezone.now(),
        )
        StripeSubscriptionFactory(
            customer__subscriber=organization, days_until_renewal=3
        )

        with self.assertNumQueries(1):
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

    @patch("core.email.send_mail")
    def test_deactivated_org_is_skipped(self, mock_send_mail):
        organization = OrganizationFactory(
            billing_email="billing@example.com", is_active=False
        )
        StripeSubscriptionFactory(
            customer__subscriber=organization, days_until_renewal=3
        )

        with self.assertNumQueries(1):
            send_expiry_reminders_task()

        mock_send_mail.assert_not_called()
