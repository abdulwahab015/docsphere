import contextlib
import json
import re
import threading
import time
import zipfile
from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import stripe
from django.conf import settings
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import (
    TestCase,
    TransactionTestCase,
    override_settings,
    skipUnlessDBFeature,
)
from django.urls import reverse
from django.utils import timezone
from djstripe.models import Price
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from audit.choices import AuditVerb
from audit.factories import AuditEventFactory
from audit.models import AuditEvent
from core.celery import app as celery_app
from core.tests import EAGER_PROPAGATES_SETTING, AssumeActiveSubscription
from notifications.factories import NotificationFactory
from notifications.models import Notification
from organizations.admin import OrganizationAdmin
from organizations.api.v1.views import EXPORT_IN_PROGRESS_MESSAGE
from organizations.choices import ExportStatus
from organizations.constants import EXPORT_MAX_RETRIES
from organizations.exports import (
    INVALID_EXPORT_LINK_MESSAGE,
    build_export,
    make_export_token,
    read_export_token,
)
from organizations.factories import (
    OrganizationFactory,
    StripeCustomerFactory,
    StripePriceFactory,
    StripeSubscriptionFactory,
)
from organizations.models import Organization, OrganizationExport
from organizations.tasks import (
    build_organization_export_task,
    purge_deleted_organizations_task,
    remove_expired_exports_task,
)
from projects.choices import AccessLevel, Visibility
from projects.factories import (
    AttachmentFactory,
    DocumentFactory,
    DocumentPermissionFactory,
    DocumentVersionFactory,
    ProjectFactory,
    ProjectPermissionFactory,
)
from projects.models import Document, Project
from projects.tests import TemporaryMediaRoot
from subscriptions.api.v1.serializers import ORGANIZATION_DELETED_MESSAGE
from users.choices import InvitationStatus
from users.factories import AdminUserFactory, InvitationFactory, UserFactory
from users.models import Invitation
from users.tests import RACE_WAIT_SECONDS

User = get_user_model()

DAY = 24 * 60 * 60


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


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class OrganizationSignupAPITests(APITestCase):
    def test_signup_creates_organization_and_admin_and_logs_in(self):
        with self.assertNumQueries(9):
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
        self.assertEqual(user.name, "")
        self.assertIsNone(user.email_verified_at)

    def test_signup_emails_the_admin_a_link_to_verify_their_address(self):
        response = self.client.post(
            reverse("organization_signup"),
            {
                "name": "Acme Inc",
                "admin_email": "admin@acme.test",
                "admin_password": "Str0ng-New-Pass!",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["admin@acme.test"])
        self.assertEqual(message.subject, "Verify your email address for DocSphere")
        self.assertIn("Acme Inc", message.body)
        self.assertIn(f"{settings.FRONTEND_URL}/verify-email?token=", message.body)

    def test_signup_takes_over_an_address_its_unverified_account_has_lost(self):
        squatter = AdminUserFactory(email="admin@acme.test", email_verified_at=None)
        User.objects.filter(pk=squatter.pk).update(
            created=timezone.now() - settings.EMAIL_LINK_EXPIRY - timedelta(minutes=1)
        )

        response = self.client.post(
            reverse("organization_signup"),
            {
                "name": "Acme Inc",
                "admin_email": "admin@acme.test",
                "admin_password": "Str0ng-New-Pass!",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(
            Organization.objects.filter(pk=squatter.organization_id).exists()
        )
        self.assertEqual(
            User.objects.get(email="admin@acme.test").organization.name, "Acme Inc"
        )

    def test_signup_records_the_admins_name(self):
        # One query fewer than above: no billing email to check for uniqueness.
        with self.assertNumQueries(8):
            response = self.client.post(
                reverse("organization_signup"),
                {
                    "name": "Acme Inc",
                    "admin_email": "admin@acme.test",
                    "admin_password": "Str0ng-New-Pass!",
                    "admin_name": " Grace Hopper ",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(email="admin@acme.test").name, "Grace Hopper")

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

        with self.assertNumQueries(8):
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

    def test_signup_rejects_an_address_still_waiting_to_be_verified(self):
        AdminUserFactory(email="admin@acme.test", email_verified_at=None)

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
        self.assertIn("admin_email", response.data)

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
                "deleted": True,
                "users": [
                    {"email": "member@unpaid.test", "role": "MEMBER"},
                    {
                        "email": "new@unpaid.test",
                        "role": "ADMIN",
                        "email_verified": False,
                    },
                ],
            },
            {
                "name": "Overdue Org",
                "subscribed": True,
                "subscription_status": "past_due",
                "require_two_factor": True,
                "users": [
                    {
                        "email": "admin@overdue.test",
                        "role": "ADMIN",
                        "two_factor_secret": "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
                    }
                ],
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
                        "attachments": ["diagram.pdf"],
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
        # Seeded attachments are stored as real files.
        self.enterContext(
            override_settings(MEDIA_ROOT=self.enterContext(TemporaryDirectory()))
        )
        seed_dir = Path(self.enterContext(TemporaryDirectory()))
        self.seed_path = seed_dir / "seed.json"
        self.seed_path.write_text(json.dumps(self.seed), encoding="utf-8")

    def test_seeds_organizations_users_and_subscriptions(self):
        with self.assertNumQueries(43):
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
        self.assertTrue(admin.email_verified)
        self.assertFalse(User.objects.get(email="new@unpaid.test").email_verified)
        # Two-factor sign-in, on for one account and required by its organization.
        self.assertFalse(admin.two_factor_enabled)
        self.assertFalse(paid.require_two_factor)
        self.assertTrue(overdue.require_two_factor)
        with_app = User.objects.get(email="admin@overdue.test")
        self.assertTrue(with_app.two_factor_enabled)
        self.assertEqual(with_app.totp_secret, "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP")

    def test_seeds_plans_and_billing_emails(self):
        with self.assertNumQueries(43):
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
        # ...and one can already be deleted, waiting to be purged.
        self.assertTrue(
            Organization.objects.get(name="Unpaid Org").deletion_requested_at
        )
        self.assertIsNone(
            Organization.objects.get(name="Paid Org").deletion_requested_at
        )

    def test_seeds_projects_with_their_owner_and_shares(self):
        with self.assertNumQueries(43):
            call_command("seed_e2e", self.seed_path, stdout=StringIO())

        roadmap = Project.objects.get(name="Roadmap")
        self.assertEqual(roadmap.created_by.email, "owner@projects.test")
        self.assertTrue(roadmap.is_active)
        self.assertEqual(
            dict(roadmap.permissions.values_list("user__email", "access_level")),
            {"owner@projects.test": "OWNER", "editor@projects.test": "EDITOR"},
        )
        # Each share shows in the activity as the owner sharing it.
        self.assertEqual(
            list(
                roadmap.audit_events.values_list(
                    "actor__email", "verb", "target_user__email", "details"
                )
            ),
            [
                (
                    "owner@projects.test",
                    "ACCESS_GRANTED",
                    "editor@projects.test",
                    {"access_level": "EDITOR"},
                )
            ],
        )
        archived = Project.objects.get(name="Archived")
        self.assertFalse(archived.is_active)
        self.assertEqual(archived.visibility, "PUBLIC")

    def test_seeds_documents_in_projects_or_personal(self):
        with self.assertNumQueries(43):
            call_command("seed_e2e", self.seed_path, stdout=StringIO())

        spec = Document.objects.get(title="Spec")
        self.assertEqual(spec.project.name, "Roadmap")
        self.assertEqual(
            dict(spec.permissions.values_list("user__email", "access_level")),
            {"owner@projects.test": "OWNER", "editor@projects.test": "VIEWER"},
        )
        self.assertEqual(
            list(
                spec.audit_events.values_list(
                    "actor__email", "verb", "target_user__email", "details"
                )
            ),
            [
                (
                    "owner@projects.test",
                    "ACCESS_GRANTED",
                    "editor@projects.test",
                    {"access_level": "VIEWER"},
                )
            ],
        )
        # ...and tells the person shared with, as sharing in the app does.
        self.assertEqual(
            list(
                spec.notifications.values_list(
                    "recipient__email", "actor__email", "verb", "details"
                )
            ),
            [
                (
                    "editor@projects.test",
                    "owner@projects.test",
                    "ACCESS_GRANTED",
                    {"access_level": "VIEWER"},
                )
            ],
        )
        attachment = spec.attachments.get()
        self.assertEqual(
            (attachment.name, attachment.content_type, attachment.uploaded_by),
            ("diagram.pdf", "application/pdf", spec.created_by),
        )
        diary = Document.objects.get(title="Diary")
        self.assertIsNone(diary.project)
        self.assertFalse(diary.is_active)
        self.assertEqual(diary.content, "Personal notes.")
        self.assertEqual(diary.organization, spec.organization)
        # Each starts its history the way a document created in the app does.
        first_version = diary.versions.get()
        self.assertEqual(
            (first_version.revision, first_version.content, first_version.created_by),
            (1, "Personal notes.", diary.created_by),
        )

    @override_settings(E2E_SEEDING_ENABLED=False)
    def test_refuses_to_run_where_seeding_is_disabled(self):
        with (
            self.assertNumQueries(0),
            self.assertRaisesMessage(CommandError, "E2E seeding is disabled"),
        ):
            call_command("seed_e2e", self.seed_path, stdout=StringIO())

        self.assertFalse(Organization.objects.exists())


class OrganizationDeletionTests(APITestCase):
    url = reverse("organization_delete")
    cancel_url = reverse("organization_delete_cancel")

    def setUp(self):
        super().setUp()
        self.org = OrganizationFactory(name="Acme", billing_email="billing@acme.test")
        self.subscription = StripeSubscriptionFactory(customer__subscriber=self.org)
        self.admin = AdminUserFactory(organization=self.org)
        self.member = UserFactory(organization=self.org)
        self.client.force_authenticate(self.admin)

    def mark_deleted(self):
        """Deleted already - on the instance the signed-in admin shares."""
        self.org.deletion_requested_at = timezone.now()
        self.org.save()

    def delete_organization(self, name="Acme", queries=0):
        with self.assertNumQueries(queries):
            return self.client.post(self.url, {"name": name})

    @patch("clients.stripe.cancel_subscription", return_value={"status": "canceled"})
    def test_an_admin_deletes_the_organization_by_typing_its_name(self, cancel):
        invitation = InvitationFactory(organization=self.org, invited_by=self.admin)
        RefreshToken.for_user(self.member)

        response = self.delete_organization(queries=15)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.org.refresh_from_db()
        self.assertTrue(self.org.deletion_requested_at)
        # Its billing email is free for another organization at once.
        self.assertIsNone(self.org.billing_email)
        cancel.assert_called_once_with(self.subscription.id)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.stripe_data["status"], "canceled")
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatus.REVOKED)
        self.assertFalse(
            OutstandingToken.objects.filter(
                user=self.member, blacklistedtoken__isnull=True
            ).exists()
        )

    @patch("clients.stripe.cancel_subscription", return_value={"status": "canceled"})
    def test_nobody_in_it_can_use_the_app_and_it_says_when_it_goes(self, _cancel):
        self.delete_organization(queries=11)
        self.org.refresh_from_db()
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(0):
            projects = self.client.get(reverse("project_list_create"))
        with self.assertNumQueries(2):
            me = self.client.get(reverse("user_me"))

        self.assertEqual(projects.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(projects.data["code"], "organization_deleted")
        self.assertEqual(
            me.data["organization"]["deletion_scheduled_for"],
            (self.org.deletion_requested_at + timedelta(days=30))
            .isoformat()
            .replace("+00:00", "Z"),
        )

    @patch("clients.stripe.cancel_subscription")
    def test_a_lapsed_organization_can_delete_itself(self, cancel):
        self.subscription.delete()

        response = self.delete_organization(queries=10)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        cancel.assert_not_called()

    @patch("clients.stripe.cancel_subscription")
    def test_a_name_that_doesnt_match_changes_nothing(self, cancel):
        response = self.delete_organization(name="acme", queries=0)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)
        self.org.refresh_from_db()
        self.assertIsNone(self.org.deletion_requested_at)
        cancel.assert_not_called()

    @patch("clients.stripe.cancel_subscription", side_effect=stripe.StripeError("down"))
    def test_if_stripe_cant_cancel_nothing_changes(self, _cancel):
        invitation = InvitationFactory(organization=self.org, invited_by=self.admin)

        response = self.delete_organization(queries=11)

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.org.refresh_from_db()
        self.assertIsNone(self.org.deletion_requested_at)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatus.PENDING)

    def test_members_cant_delete_it(self):
        self.client.force_authenticate(self.member)

        response = self.delete_organization(queries=0)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deleting_it_twice_is_refused(self):
        self.mark_deleted()

        response = self.delete_organization(queries=0)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_an_admin_restores_it_and_it_needs_a_new_subscription(self):
        self.subscription.delete()
        self.mark_deleted()

        with self.assertNumQueries(1):
            response = self.client.post(self.cancel_url)
        with self.assertNumQueries(2):
            projects = self.client.get(reverse("project_list_create"))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.org.refresh_from_db()
        self.assertIsNone(self.org.deletion_requested_at)
        self.assertEqual(projects.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_restoring_one_that_isnt_deleted_is_refused(self):
        with self.assertNumQueries(0):
            response = self.client.post(self.cancel_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_it_cant_subscribe_while_deleted(self):
        self.subscription.delete()
        self.mark_deleted()
        price = StripePriceFactory()

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("subscriptions_checkout"), {"price_id": price.id}
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(ORGANIZATION_DELETED_MESSAGE, str(response.data))


class OrganizationPurgeTests(TemporaryMediaRoot, TestCase):
    def setUp(self):
        super().setUp()
        self.org = OrganizationFactory()
        admin = AdminUserFactory(organization=self.org)
        member = UserFactory(organization=self.org)
        project = ProjectFactory(organization=self.org, created_by=admin)
        ProjectPermissionFactory(project=project, user=member)
        self.document = DocumentFactory(project=project, created_by=member)
        DocumentVersionFactory(document=self.document, created_by=member)
        DocumentPermissionFactory(document=self.document, user=admin)
        self.attachment = AttachmentFactory(document=self.document, uploaded_by=member)
        InvitationFactory(organization=self.org, invited_by=admin)
        AuditEventFactory(organization=self.org, actor=admin, target_user=member)
        NotificationFactory(recipient=member, actor=admin, document=self.document)
        self.other_document = DocumentFactory()
        self.export = OrganizationExport.objects.create(
            organization=self.org, requested_by=admin
        )
        build_export(self.export)

    def deleted_days_ago(self, days):
        Organization.objects.filter(pk=self.org.pk).update(
            deletion_requested_at=timezone.now() - timedelta(days=days)
        )

    def test_an_organization_deleted_over_30_days_ago_is_purged_entirely(self):
        self.deleted_days_ago(31)
        stored = self.attachment.file.name

        with self.captureOnCommitCallbacks(execute=True):
            purge_deleted_organizations_task()

        org_id = self.org.pk
        self.assertFalse(Organization.objects.filter(pk=org_id).exists())
        self.assertFalse(User.objects.filter(organization_id=org_id).exists())
        self.assertFalse(Project.objects.filter(organization_id=org_id).exists())
        self.assertFalse(Document.objects.filter(organization_id=org_id).exists())
        self.assertFalse(Invitation.objects.filter(organization_id=org_id).exists())
        self.assertFalse(AuditEvent.objects.filter(organization_id=org_id).exists())
        self.assertFalse(Notification.objects.exists())
        self.assertFalse(default_storage.exists(stored))
        self.assertFalse(default_storage.exists(self.export.file.name))
        # Other organizations are untouched.
        self.assertTrue(Document.objects.filter(pk=self.other_document.pk).exists())

    def test_one_deleted_more_recently_is_kept(self):
        self.deleted_days_ago(29)

        purge_deleted_organizations_task()

        self.assertTrue(Organization.objects.filter(pk=self.org.pk).exists())
        self.assertTrue(default_storage.exists(self.attachment.file.name))


class OrganizationExportTests(
    TemporaryMediaRoot, AssumeActiveSubscription, APITestCase
):
    create_url = reverse("organization_export_create")
    download_url = reverse("organization_export_download")

    def setUp(self):
        super().setUp()
        self.org = OrganizationFactory(name="Acme")
        self.admin = AdminUserFactory(organization=self.org, email="ada@acme.test")
        self.member = UserFactory(organization=self.org, email="mia@acme.test")
        self.client.force_authenticate(self.admin)

    def make_export(self, status=ExportStatus.READY):
        export = OrganizationExport.objects.create(
            organization=self.org, requested_by=self.admin, status=status
        )
        build_export(export)
        return export

    def read_export(self, export):
        with zipfile.ZipFile(export.file.open("rb")) as archive:
            return {
                name: (
                    json.loads(archive.read(name))
                    if name.endswith(".json")
                    else archive.read(name)
                )
                for name in archive.namelist()
            }

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_an_admin_asks_for_an_export_and_is_emailed_a_link(self):
        with (
            self.assertNumQueries(16),
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post(self.create_url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        export = OrganizationExport.objects.get()
        self.assertEqual(export.status, ExportStatus.READY)
        self.assertTrue(export.file)
        self.assertEqual(
            list(AuditEvent.objects.values_list("actor", "verb")),
            [(self.admin.pk, AuditVerb.EXPORT_REQUESTED)],
        )
        self.assertEqual(mail.outbox[0].to, ["ada@acme.test"])
        # The link's token names this export (read back rather than signed
        # again: a token carries the second it was signed in).
        token = re.search(
            r"/settings/organization/export\?token=(\S+)", mail.outbox[0].body
        ).group(1)
        self.assertEqual(read_export_token(token), export.pk)

    def test_it_holds_only_what_the_admin_can_open(self):
        shared = DocumentFactory(
            project=None,
            organization=self.org,
            created_by=self.member,
            title="Shared",
            content="Shared text",
        )
        DocumentPermissionFactory(
            document=shared, user=self.member, access_level=AccessLevel.OWNER
        )
        DocumentPermissionFactory(
            document=shared, user=self.admin, access_level=AccessLevel.VIEWER
        )
        AttachmentFactory(document=shared, uploaded_by=self.member, name="a.pdf")
        DocumentFactory(
            project=None,
            organization=self.org,
            created_by=self.member,
            title="Private",
            content="Secret text",
        )
        ProjectFactory(
            organization=self.org,
            created_by=self.admin,
            name="Roadmap",
            visibility=Visibility.PUBLIC,
        )
        ProjectFactory(organization=self.org, created_by=self.member, name="Layoffs")
        DocumentFactory(title="Elsewhere")

        contents = self.read_export(self.make_export())

        self.assertEqual(
            [document["title"] for document in contents["documents.json"]], ["Shared"]
        )
        self.assertEqual(contents["documents.json"][0]["content"], "Shared text")
        self.assertEqual(
            contents["documents.json"][0]["shared_with"],
            [
                {"email": "mia@acme.test", "access_level": "OWNER"},
                {"email": "ada@acme.test", "access_level": "VIEWER"},
            ],
        )
        self.assertEqual(
            [project["name"] for project in contents["projects.json"]], ["Roadmap"]
        )
        self.assertEqual(
            contents["organization.json"]["not_included"],
            {"private_projects": 1, "private_documents": 1},
        )
        self.assertEqual(
            [member["email"] for member in contents["members.json"]],
            ["ada@acme.test", "mia@acme.test"],
        )
        attachment_path = contents["documents.json"][0]["attachments"][0]
        self.assertTrue(attachment_path.endswith("-a.pdf"))
        self.assertIn(attachment_path, contents)
        self.assertNotIn("Secret text", str(contents))
        self.assertNotIn("Elsewhere", str(contents))

    def test_an_admin_downloads_it_from_the_link(self):
        export = self.make_export()

        with self.assertNumQueries(2):
            response = self.client.get(
                self.download_url, {"token": make_export_token(export)}
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            list(AuditEvent.objects.values_list("actor", "verb")),
            [(self.admin.pk, AuditVerb.EXPORT_DOWNLOADED)],
        )
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertTrue(b"".join(response.streaming_content).startswith(b"PK"))

    def test_an_expired_or_altered_link_is_refused(self):
        export = self.make_export()
        token = make_export_token(export)

        with self.assertNumQueries(0):
            altered = self.client.get(self.download_url, {"token": token + "x"})
        with (
            patch("django.core.signing.time.time", return_value=time.time() + 8 * DAY),
            self.assertNumQueries(0),
        ):
            expired = self.client.get(self.download_url, {"token": token})

        self.assertEqual(altered.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(expired.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(expired.data["detail"]), INVALID_EXPORT_LINK_MESSAGE)

    def test_another_organizations_export_is_not_found(self):
        other_admin = AdminUserFactory()
        theirs = OrganizationExport.objects.create(
            organization=other_admin.organization,
            requested_by=other_admin,
            status=ExportStatus.READY,
        )
        build_export(theirs)

        with self.assertNumQueries(1):
            response = self.client.get(
                self.download_url, {"token": make_export_token(theirs)}
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_one_at_a_time_while_an_export_is_being_built(self):
        self.make_export(status=ExportStatus.BUILDING)

        with self.assertNumQueries(5):
            response = self.client.post(self.create_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data["detail"]), EXPORT_IN_PROGRESS_MESSAGE)
        self.assertEqual(OrganizationExport.objects.count(), 1)
        self.assertFalse(AuditEvent.objects.exists())

    @patch("organizations.api.v1.views.build_organization_export_task.delay")
    def test_a_finished_failed_or_long_stuck_export_doesnt_block_another(self, _build):
        self.make_export(status=ExportStatus.READY)
        self.make_export(status=ExportStatus.FAILED)
        stuck = self.make_export(status=ExportStatus.BUILDING)
        OrganizationExport.objects.filter(pk=stuck.pk).update(
            created=timezone.now() - timedelta(hours=2)
        )

        with self.assertNumQueries(6), self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.create_url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    @patch("organizations.api.v1.views.build_organization_export_task.delay")
    def test_the_daily_limit_counts_the_whole_organization(self, _build):
        other_admin = AdminUserFactory(organization=self.org)
        cache.clear()
        statuses = []

        with patch.object(
            ScopedRateThrottle, "THROTTLE_RATES", {"organization_export": "2/day"}
        ):
            for admin in (self.admin, other_admin, other_admin):
                OrganizationExport.objects.update(status=ExportStatus.READY)
                self.client.force_authenticate(admin)
                statuses.append(self.client.post(self.create_url).status_code)

        self.assertEqual(
            statuses,
            [
                status.HTTP_202_ACCEPTED,
                status.HTTP_202_ACCEPTED,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ],
        )

    def test_one_still_building_or_failed_cant_be_downloaded(self):
        building = self.make_export(status=ExportStatus.BUILDING)
        failed = self.make_export(status=ExportStatus.FAILED)

        for export in (building, failed):
            with self.assertNumQueries(1):
                response = self.client.get(
                    self.download_url, {"token": make_export_token(export)}
                )
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_members_cant_ask_for_or_download_one(self):
        export = self.make_export()
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(0):
            asked = self.client.post(self.create_url)
        with self.assertNumQueries(0):
            downloaded = self.client.get(
                self.download_url, {"token": make_export_token(export)}
            )

        self.assertEqual(asked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(downloaded.status_code, status.HTTP_403_FORBIDDEN)

    def test_exports_older_than_a_week_are_removed_daily(self):
        kept, expired = self.make_export(), self.make_export()
        OrganizationExport.objects.filter(pk=expired.pk).update(
            created=timezone.now() - timedelta(days=8)
        )
        stored = expired.file.name

        with self.assertNumQueries(2):
            remove_expired_exports_task()

        self.assertQuerySetEqual(OrganizationExport.objects.all(), [kept])
        self.assertFalse(default_storage.exists(stored))
        self.assertTrue(default_storage.exists(kept.file.name))


class ExportBuildRetryTests(TemporaryMediaRoot, TestCase):
    def setUp(self):
        super().setUp()
        admin = AdminUserFactory(email="ada@acme.test")
        self.export = OrganizationExport.objects.create(
            organization=admin.organization, requested_by=admin
        )
        # Eager, but letting Celery run the retries rather than raise its
        # internal Retry; the outcome is read from the result.
        propagates = celery_app.conf[EAGER_PROPAGATES_SETTING]
        celery_app.conf[EAGER_PROPAGATES_SETTING] = False
        self.addCleanup(
            celery_app.conf.__setitem__, EAGER_PROPAGATES_SETTING, propagates
        )

    @patch("organizations.tasks.build_export")
    def test_a_failed_build_is_tried_again_until_it_works(self, build):
        build.side_effect = [OSError("No space left on device"), None]

        with self.assertNumQueries(4):
            result = build_organization_export_task.delay(self.export.pk)

        self.assertTrue(result.successful())
        self.assertEqual(build.call_count, 2)
        self.export.refresh_from_db()
        self.assertEqual(self.export.status, ExportStatus.READY)
        self.assertIn("is ready", mail.outbox[0].subject)

    @patch("organizations.tasks.build_export", side_effect=OSError("Disk full"))
    def test_after_its_retries_it_is_marked_failed_and_the_admin_told(self, build):
        with self.assertNumQueries(6):
            result = build_organization_export_task.delay(self.export.pk)

        self.assertIsInstance(result.result, OSError)
        self.assertEqual(build.call_count, EXPORT_MAX_RETRIES + 1)
        self.export.refresh_from_db()
        self.assertEqual(self.export.status, ExportStatus.FAILED)
        self.assertEqual(mail.outbox[0].to, ["ada@acme.test"])
        self.assertIn("failed", mail.outbox[0].subject)
        self.assertIn("/settings/organization", mail.outbox[0].body)


@skipUnlessDBFeature("has_select_for_update")
class ConcurrentExportRequestTests(AssumeActiveSubscription, TransactionTestCase):
    """Real concurrent requests, so only on a database with row locks
    (Postgres: CI and `make test-pg`)."""

    @patch("organizations.api.v1.views.build_organization_export_task.delay")
    def test_two_requests_at_once_start_one_export(self, _build):
        admins = AdminUserFactory.create_batch(2, organization=OrganizationFactory())
        both_checked = threading.Barrier(2)
        create_export = OrganizationExport.objects.create
        responses = []

        def create_after_the_other_checked(**fields):
            with contextlib.suppress(threading.BrokenBarrierError):
                both_checked.wait(timeout=RACE_WAIT_SECONDS)
            return create_export(**fields)

        def ask(admin):
            client = APIClient()
            client.force_authenticate(admin)
            try:
                responses.append(client.post(reverse("organization_export_create")))
            finally:
                connection.close()

        with patch.object(
            OrganizationExport.objects,
            "create",
            side_effect=create_after_the_other_checked,
        ):
            requests = [threading.Thread(target=ask, args=(admin,)) for admin in admins]
            for request in requests:
                request.start()
            for request in requests:
                request.join()

        self.assertEqual(
            sorted(response.status_code for response in responses),
            [status.HTTP_202_ACCEPTED, status.HTTP_400_BAD_REQUEST],
        )
        self.assertEqual(OrganizationExport.objects.count(), 1)
