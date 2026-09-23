from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from organizations.admin import OrganizationAdmin
from organizations.factories import (
    OrganizationFactory,
    StripeCustomerFactory,
    StripeSubscriptionFactory,
)
from organizations.models import Organization
from users.factories import AdminUserFactory, UserFactory

User = get_user_model()


class OrganizationModelTests(TestCase):
    def test_str_is_the_name(self):
        org = OrganizationFactory(name="Acme Inc")

        self.assertEqual(str(org), "Acme Inc")

    def test_email_property_aliases_billing_email(self):
        org = OrganizationFactory(billing_email="billing@acme.test")

        self.assertEqual(org.email, "billing@acme.test")

    def test_active_subscription_returns_the_active_subscription(self):
        org = OrganizationFactory()
        subscription = StripeSubscriptionFactory(customer__subscriber=org)

        with self.assertNumQueries(2):
            self.assertEqual(org.active_subscription, subscription)

    def test_active_subscription_is_none_without_a_customer(self):
        org = OrganizationFactory()

        with self.assertNumQueries(1):
            self.assertIsNone(org.active_subscription)

    def test_active_subscription_is_none_when_customer_has_no_active_sub(self):
        org = OrganizationFactory()
        StripeCustomerFactory(subscriber=org)

        with self.assertNumQueries(2):
            self.assertIsNone(org.active_subscription)

    def test_active_subscription_ignores_a_canceled_subscription(self):
        org = OrganizationFactory()
        StripeSubscriptionFactory(customer__subscriber=org, status="canceled")

        with self.assertNumQueries(2):
            self.assertIsNone(org.active_subscription)


class OrganizationAdminActionTests(TestCase):
    def setUp(self):
        self.model_admin = OrganizationAdmin(Organization, AdminSite())

    def test_deactivate_organizations_sets_is_active_false(self):
        org = OrganizationFactory(is_active=True)

        self.model_admin.deactivate_organizations(
            request=None, queryset=Organization.objects.filter(pk=org.pk)
        )

        org.refresh_from_db()
        self.assertFalse(org.is_active)

    def test_activate_organizations_sets_is_active_true(self):
        org = OrganizationFactory(is_active=False)

        self.model_admin.activate_organizations(
            request=None, queryset=Organization.objects.filter(pk=org.pk)
        )

        org.refresh_from_db()
        self.assertTrue(org.is_active)


class OrganizationSignupAPITests(APITestCase):
    def test_signup_creates_organization_and_admin_and_logs_in(self):
        with self.assertNumQueries(7):
            response = self.client.post(
                reverse("organization_signup"),
                {
                    "name": "Acme Inc",
                    "billing_email": "billing@acme.test",
                    "admin_email": "admin@acme.test",
                    "admin_password": "Str0ng-New-Pass!",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        organization = Organization.objects.get(name="Acme Inc")
        self.assertEqual(organization.billing_email, "billing@acme.test")

        user = User.objects.get(email="admin@acme.test")
        self.assertEqual(user.organization, organization)
        self.assertEqual(user.org_role, "ADMIN")
        self.assertTrue(user.check_password("Str0ng-New-Pass!"))

    def test_signup_without_billing_email_succeeds(self):
        response = self.client.post(
            reverse("organization_signup"),
            {
                "name": "Acme Inc",
                "admin_email": "admin@acme.test",
                "admin_password": "Str0ng-New-Pass!",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        organization = Organization.objects.get(name="Acme Inc")
        self.assertIsNone(organization.billing_email)

    def test_signup_rejects_duplicate_billing_email(self):
        OrganizationFactory(billing_email="billing@acme.test")

        with self.assertNumQueries(2):
            response = self.client.post(
                reverse("organization_signup"),
                {
                    "name": "Acme Inc",
                    "billing_email": "billing@acme.test",
                    "admin_email": "admin@acme.test",
                    "admin_password": "Str0ng-New-Pass!",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="admin@acme.test").exists())

    def test_signup_rejects_duplicate_admin_email(self):
        UserFactory(email="admin@acme.test")

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("organization_signup"),
                {
                    "name": "Acme Inc",
                    "admin_email": "admin@acme.test",
                    "admin_password": "Str0ng-New-Pass!",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Organization.objects.filter(name="Acme Inc").count(), 0)

    def test_signup_rejects_a_password_missing_a_character_class(self):
        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("organization_signup"),
                {
                    "name": "Acme Inc",
                    "admin_email": "admin@acme.test",
                    "admin_password": "alllowercase1",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Organization.objects.filter(name="Acme Inc").exists())

    def test_signup_is_rate_limited(self):
        cache.clear()
        with patch.object(
            ScopedRateThrottle, "THROTTLE_RATES", {"org_signup": "1/min"}
        ):
            self.client.post(
                reverse("organization_signup"),
                {
                    "name": "Acme Inc",
                    "admin_email": "admin@acme.test",
                    "admin_password": "Str0ng-New-Pass!",
                },
            )
            with self.assertNumQueries(0):
                throttled = self.client.post(
                    reverse("organization_signup"),
                    {
                        "name": "Other Inc",
                        "admin_email": "other@acme.test",
                        "admin_password": "Str0ng-New-Pass!",
                    },
                )

        self.assertEqual(throttled.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class OrganizationProfileAPITests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory(name="Acme Inc", billing_email=None)
        self.admin = AdminUserFactory(email="admin@acme.test", organization=self.org)
        self.member = UserFactory(email="member@acme.test", organization=self.org)

    def test_admin_can_retrieve_own_organization(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(1):
            response = self.client.get(reverse("organization_profile"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Acme Inc")
        self.assertIsNone(response.data["active_subscription"])

    def test_retrieve_includes_the_active_subscription_summary(self):
        customer = StripeCustomerFactory(subscriber=self.org)
        StripeSubscriptionFactory(
            id="sub_profile",
            customer=customer,
            stripe_data={
                "id": "sub_profile",
                "status": "active",
                "cancel_at_period_end": False,
                "plan": {"interval": "month"},
                "items": {"data": [{"current_period_end": 1792323428}]},
            },
        )
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(2):
            response = self.client.get(reverse("organization_profile"))

        subscription = response.data["active_subscription"]
        self.assertEqual(subscription["id"], "sub_profile")
        self.assertEqual(subscription["status"], "active")
        self.assertEqual(subscription["interval"], "month")
        self.assertFalse(subscription["cancel_at_period_end"])
        self.assertEqual(
            subscription["current_period_end"].isoformat(), "2026-10-18T11:37:08+00:00"
        )

    def test_retrieve_omits_a_non_active_subscription(self):
        customer = StripeCustomerFactory(subscriber=self.org)
        StripeSubscriptionFactory(customer=customer, status="canceled")
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(2):
            response = self.client.get(reverse("organization_profile"))

        self.assertIsNone(response.data["active_subscription"])

    def test_retrieve_tolerates_a_subscription_without_a_period_end(self):
        customer = StripeCustomerFactory(subscriber=self.org)
        StripeSubscriptionFactory(
            customer=customer,
            stripe_data={"id": "sub_bare", "status": "active"},
        )
        self.client.force_authenticate(self.admin)

        response = self.client.get(reverse("organization_profile"))

        self.assertIsNone(response.data["active_subscription"]["current_period_end"])
        self.assertIsNone(response.data["active_subscription"]["interval"])

    def test_admin_can_set_billing_email(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(4):
            response = self.client.patch(
                reverse("organization_profile"), {"billing_email": "billing@acme.test"}
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.org.refresh_from_db()
        self.assertEqual(self.org.billing_email, "billing@acme.test")

    def test_update_rejects_a_billing_email_already_used_by_another_organization(self):
        OrganizationFactory(billing_email="taken@acme.test")
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(1):
            response = self.client.patch(
                reverse("organization_profile"), {"billing_email": "taken@acme.test"}
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_keeping_own_billing_email_succeeds(self):
        self.org.billing_email = "billing@acme.test"
        self.org.save(update_fields=["billing_email"])
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            reverse("organization_profile"),
            {"billing_email": "billing@acme.test", "name": "Acme Incorporated"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_admin_cannot_access_organization_profile(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(0):
            response = self.client.get(reverse("organization_profile"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reachable_without_an_active_subscription(self):
        """An org with no active subscription must still be able to fix its
        billing_email, since that's the prerequisite for checkout to work."""
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            reverse("organization_profile"), {"billing_email": "billing@acme.test"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
