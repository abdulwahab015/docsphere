from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from organizations.factories import OrganizationFactory
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
