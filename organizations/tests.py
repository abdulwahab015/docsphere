import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import stripe
from django.conf import settings
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from djstripe.models import Price
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
from projects.models import Document, Project
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
        self.assertEqual(
            response.cookies[settings.REFRESH_COOKIE_NAME].value,
            response.data["refresh"],
        )

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

    def test_signup_with_a_null_billing_email_ignores_other_organizations_without_one(
        self,
    ):
        OrganizationFactory(billing_email=None)

        with self.assertNumQueries(6):
            response = self.client.post(
                reverse("organization_signup"),
                {
                    "name": "Acme Inc",
                    "billing_email": None,
                    "admin_email": "admin@acme.test",
                    "admin_password": "Str0ng-New-Pass!",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(Organization.objects.get(name="Acme Inc").billing_email)

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
        self.assertIn("admin_password", response.data)
        self.assertNotIn("non_field_errors", response.data)
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

    def test_schema_documents_the_active_subscription_as_nullable(self):
        with self.assertNumQueries(0):
            response = self.client.get(reverse("schema"), {"format": "json"})

        active_subscription = response.data["components"]["schemas"]["Organization"][
            "properties"
        ]["active_subscription"]
        self.assertTrue(active_subscription["nullable"])

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

        with self.assertNumQueries(7):
            response = self.client.patch(
                reverse("organization_profile"), {"billing_email": "billing@acme.test"}
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.org.refresh_from_db()
        self.assertEqual(self.org.billing_email, "billing@acme.test")

    @patch("stripe.Customer.modify")
    def test_a_new_billing_email_reaches_the_stripe_customer(
        self, mock_customer_modify
    ):
        customer = StripeCustomerFactory(subscriber=self.org)
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(8):
            response = self.client.patch(
                reverse("organization_profile"), {"billing_email": "billing@acme.test"}
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_customer_modify.assert_called_once()
        self.assertEqual(mock_customer_modify.call_args.args, (customer.id,))
        self.assertEqual(
            mock_customer_modify.call_args.kwargs["email"], "billing@acme.test"
        )

    @patch("stripe.Customer.modify")
    def test_nothing_is_saved_when_stripe_cannot_be_updated(self, mock_customer_modify):
        mock_customer_modify.side_effect = stripe.APIConnectionError("Network down")
        StripeCustomerFactory(subscriber=self.org)
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(7):
            response = self.client.patch(
                reverse("organization_profile"), {"billing_email": "billing@acme.test"}
            )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("nothing was changed", response.data["detail"])
        self.org.refresh_from_db()
        self.assertIsNone(self.org.billing_email)

    @patch("stripe.Customer.modify")
    def test_renaming_leaves_stripe_alone(self, mock_customer_modify):
        StripeCustomerFactory(subscriber=self.org)
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(5):
            response = self.client.patch(
                reverse("organization_profile"), {"name": "Acme Labs"}
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_customer_modify.assert_not_called()

    def test_update_rejects_a_billing_email_already_used_by_another_organization(self):
        OrganizationFactory(billing_email="taken@acme.test")
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(1):
            response = self.client.patch(
                reverse("organization_profile"), {"billing_email": "taken@acme.test"}
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_clear_the_billing_email_while_others_have_none(self):
        self.org.billing_email = "billing@acme.test"
        self.org.save(update_fields=["billing_email"])
        OrganizationFactory(billing_email=None)
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(5):
            response = self.client.patch(
                reverse("organization_profile"),
                {"billing_email": None},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.org.refresh_from_db()
        self.assertIsNone(self.org.billing_email)

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


class SeedE2ECommandTests(TestCase):
    seed = {
        "password": "Seed-Pass-123!",
        "prices": [
            {"nickname": "Monthly", "unit_amount": 1500, "interval": "month"},
            {"nickname": "Yearly", "unit_amount": 15000, "interval": "year"},
        ],
        "organizations": [
            {
                "name": "Paid Org",
                "billing_email": "billing@paid.test",
                "subscribed": True,
                "users": [{"email": "admin@paid.test", "role": "ADMIN"}],
                "extra_members": 2,
            },
            {
                "name": "Unpaid Org",
                "subscribed": False,
                "users": [{"email": "member@unpaid.test", "role": "MEMBER"}],
            },
            {
                "name": "Overdue Org",
                "subscribed": True,
                "subscription_status": "past_due",
                "users": [{"email": "admin@overdue.test", "role": "ADMIN"}],
            },
            {
                "name": "Project Org",
                "subscribed": True,
                "users": [
                    {"email": "owner@projects.test", "role": "ADMIN"},
                    {"email": "editor@projects.test", "role": "MEMBER"},
                ],
                "projects": [
                    {
                        "name": "Roadmap",
                        "visibility": "PRIVATE",
                        "owner": "owner@projects.test",
                        "shared_with": {"editor@projects.test": "EDITOR"},
                    },
                    {
                        "name": "Archived",
                        "visibility": "PUBLIC",
                        "owner": "owner@projects.test",
                        "in_trash": True,
                    },
                ],
                "documents": [
                    {
                        "title": "Spec",
                        "visibility": "PRIVATE",
                        "owner": "owner@projects.test",
                        "project": "Roadmap",
                        "shared_with": {"editor@projects.test": "VIEWER"},
                    },
                    {
                        "title": "Diary",
                        "content": "Personal notes.",
                        "visibility": "PRIVATE",
                        "owner": "editor@projects.test",
                        "in_trash": True,
                    },
                ],
            },
        ],
    }

    def setUp(self):
        seed_dir = Path(self.enterContext(TemporaryDirectory()))
        self.seed_path = seed_dir / "seed.json"
        self.seed_path.write_text(json.dumps(self.seed), encoding="utf-8")

    def test_seeds_organizations_users_and_subscriptions(self):
        with self.assertNumQueries(35):
            call_command("seed_e2e", self.seed_path, stdout=StringIO())

        paid = Organization.objects.get(name="Paid Org")
        unpaid = Organization.objects.get(name="Unpaid Org")
        overdue = Organization.objects.get(name="Overdue Org")
        self.assertEqual(paid.active_subscription.stripe_data["status"], "active")
        self.assertIsNone(unpaid.active_subscription)
        self.assertEqual(overdue.active_subscription.stripe_data["status"], "past_due")
        self.assertEqual(paid.users.count(), 3)
        admin = User.objects.get(email="admin@paid.test")
        self.assertEqual(admin.org_role, "ADMIN")
        self.assertTrue(admin.check_password("Seed-Pass-123!"))

    def test_seeds_plans_and_billing_emails(self):
        with self.assertNumQueries(35):
            call_command("seed_e2e", self.seed_path, stdout=StringIO())

        prices = Price.objects.order_by("stripe_data__unit_amount")
        self.assertEqual(
            [
                (price.nickname, price.stripe_data["unit_amount"], price.product.name)
                for price in prices
            ],
            [("Monthly", 1500, "DocSphere"), ("Yearly", 15000, "DocSphere")],
        )
        self.assertEqual(prices.first().product_id, settings.STRIPE_PRODUCT_ID)
        self.assertEqual(prices.last().stripe_data["recurring"], {"interval": "year"})
        self.assertEqual(
            Organization.objects.get(name="Paid Org").billing_email, "billing@paid.test"
        )
        self.assertIsNone(Organization.objects.get(name="Unpaid Org").billing_email)

    def test_seeds_projects_with_their_owner_and_shares(self):
        with self.assertNumQueries(35):
            call_command("seed_e2e", self.seed_path, stdout=StringIO())

        roadmap = Project.objects.get(name="Roadmap")
        self.assertEqual(roadmap.created_by.email, "owner@projects.test")
        self.assertTrue(roadmap.is_active)
        self.assertEqual(
            dict(roadmap.permissions.values_list("user__email", "access_level")),
            {"owner@projects.test": "OWNER", "editor@projects.test": "EDITOR"},
        )
        archived = Project.objects.get(name="Archived")
        self.assertFalse(archived.is_active)
        self.assertEqual(archived.visibility, "PUBLIC")

    def test_seeds_documents_in_projects_or_personal(self):
        with self.assertNumQueries(35):
            call_command("seed_e2e", self.seed_path, stdout=StringIO())

        spec = Document.objects.get(title="Spec")
        self.assertEqual(spec.project.name, "Roadmap")
        self.assertEqual(
            dict(spec.permissions.values_list("user__email", "access_level")),
            {"owner@projects.test": "OWNER", "editor@projects.test": "VIEWER"},
        )
        diary = Document.objects.get(title="Diary")
        self.assertIsNone(diary.project)
        self.assertFalse(diary.is_active)
        self.assertEqual(diary.content, "Personal notes.")
        self.assertEqual(diary.organization, spec.organization)

    @override_settings(E2E_SEEDING_ENABLED=False)
    def test_refuses_to_run_where_seeding_is_disabled(self):
        with (
            self.assertNumQueries(0),
            self.assertRaisesMessage(CommandError, "E2E seeding is disabled"),
        ):
            call_command("seed_e2e", self.seed_path, stdout=StringIO())

        self.assertFalse(Organization.objects.exists())
