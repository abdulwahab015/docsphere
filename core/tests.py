import json
import logging
from unittest.mock import patch

import stripe
from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase

from core.logging.formatters import JSONFormatter
from core.middleware.logging import _redact
from core.permissions import HasActiveSubscription, SubscriptionRequired
from core.testing import AssumeActiveSubscription
from organizations.factories import (
    StripeCustomerFactory,
    StripeSubscriptionFactory,
    WebhookEndpointFactory,
)
from users.factories import AdminUserFactory, InvitationFactory, UserFactory


class RedactTests(SimpleTestCase):
    def test_redacts_by_sensitive_key_name(self):
        out = _redact({"refresh": "abc", "keep": "visible"})

        self.assertEqual(out, {"refresh": "[redacted]", "keep": "visible"})

    def test_redacts_jwt_shaped_value_under_any_key(self):
        jwt = "eyJhbGci.eyJzdWIi.sig-nature_x"
        out = _redact({"note": jwt, "count": 3})

        self.assertEqual(out, {"note": "[redacted]", "count": 3})

    def test_recurses_into_lists_and_nested_dicts(self):
        out = _redact({"items": [{"token": "t"}, {"ok": 1}]})

        self.assertEqual(out, {"items": [{"token": "[redacted]"}, {"ok": 1}]})


class JSONFormatterTests(SimpleTestCase):
    def setUp(self):
        self.formatter = JSONFormatter()

    def _record(self, **extra):
        record = logging.LogRecord(
            name="core.request",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        record.__dict__.update(extra)
        return record

    def test_renders_core_fields_and_interpolated_message(self):
        payload = json.loads(self.formatter.format(self._record()))

        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["logger"], "core.request")
        self.assertEqual(payload["message"], "hello world")
        self.assertIn("timestamp", payload)

    def test_promotes_known_request_extras_only(self):
        payload = json.loads(
            self.formatter.format(self._record(request_id="abc", ignored="x"))
        )

        self.assertEqual(payload["request_id"], "abc")
        self.assertNotIn("ignored", payload)

    def test_includes_exception_text_when_present(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = self._record()
            record.exc_info = sys.exc_info()

        payload = json.loads(self.formatter.format(record))

        self.assertIn("ValueError: boom", payload["exception"])


class RequestLoggingMiddlewareTests(APITestCase):
    def test_logs_paired_request_and_response_records(self):
        with (
            self.assertLogs("core.request", level="INFO") as captured,
            self.assertNumQueries(1),
        ):
            response = self.client.post(
                reverse("auth_login"),
                {"email": "nobody@example.com", "password": "wrong"},
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.assertEqual(len(captured.records), 2)
        started, finished = captured.records
        self.assertEqual(started.request_id, finished.request_id)
        self.assertEqual(started.method, "POST")
        self.assertEqual(finished.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIsNone(finished.user_id)

    def test_response_body_is_truncated_to_the_configured_limit(self):
        with (
            self.settings(MAX_LOG_BODY_CHARS=10),
            self.assertLogs("core.request", level="INFO") as captured,
            self.assertNumQueries(1),
        ):
            self.client.post(
                reverse("auth_login"),
                {"email": "nobody@example.com", "password": "wrong"},
            )

        self.assertIn("…", captured.records[1].getMessage())

    def test_sensitive_response_values_are_redacted_in_the_log(self):
        user = UserFactory(password="S3cret-pass!", organization=None)

        with (
            self.assertLogs("core.request", level="INFO") as captured,
            self.assertNumQueries(2),
        ):
            response = self.client.post(
                reverse("auth_login"),
                {"email": user.email, "password": "S3cret-pass!"},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["access"])  # a real token reached the client

        logged = captured.records[1].getMessage()
        self.assertIn('"access": "[redacted]"', logged)
        self.assertIn('"refresh": "[redacted]"', logged)
        self.assertNotIn(response.data["access"], logged)

    def test_skipped_paths_produce_no_log_records(self):
        with self.assertNoLogs("core.request", level="INFO"):
            self.client.get(reverse("healthz"))

    def test_forwarded_for_is_ignored_unless_the_proxy_is_trusted(self):
        with (
            self.assertLogs("core.request", level="INFO") as captured,
            self.assertNumQueries(1),
        ):
            self.client.post(
                reverse("auth_login"),
                {"email": "nobody@example.com", "password": "wrong"},
                HTTP_X_FORWARDED_FOR="1.2.3.4, 10.0.0.1",
            )

        # Default REQUEST_LOG_TRUST_FORWARDED_FOR is False → peer address only.
        self.assertEqual(captured.records[0].client_ip, "127.0.0.1")

    def test_trusted_forwarded_for_uses_the_right_most_entry(self):
        with (
            self.settings(REQUEST_LOG_TRUST_FORWARDED_FOR=True),
            self.assertLogs("core.request", level="INFO") as captured,
            self.assertNumQueries(1),
        ):
            self.client.post(
                reverse("auth_login"),
                {"email": "nobody@example.com", "password": "wrong"},
                HTTP_X_FORWARDED_FOR="1.2.3.4, 10.0.0.1",
            )

        # Left of the proxy-appended entry is client-controlled; take the last.
        self.assertEqual(captured.records[0].client_ip, "10.0.0.1")


class DefaultPaginationTests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.admin = AdminUserFactory()
        InvitationFactory(organization=self.admin.organization, invited_by=self.admin)

    def test_list_endpoints_return_the_paginated_envelope(self):
        self.client.force_authenticate(self.admin)

        # 1 COUNT for pagination + 1 SELECT for the page.
        with self.assertNumQueries(2):
            response = self.client.get(reverse("invitation_list_create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {"count", "next", "previous", "results"})
        self.assertEqual(response.data["count"], 1)


class HealthzTests(APITestCase):
    def test_healthz_reports_ok_with_a_single_db_probe(self):
        with self.assertNumQueries(1):
            response = self.client.get(reverse("healthz"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"status": "ok"})

    def test_healthz_reports_503_when_the_db_probe_fails(self):
        # DB deliberately broken — query counting is moot here.
        with patch("core.health.connection.cursor", side_effect=Exception("db down")):
            response = self.client.get(reverse("healthz"))

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data, {"status": "unhealthy"})


class HasActiveSubscriptionUnitTests(TestCase):
    """The permission in isolation - the branches that don't need a live
    endpoint carrying it."""

    @staticmethod
    def _check(user):
        request = APIRequestFactory().get("/")
        request.user = user
        return HasActiveSubscription().has_permission(request, view=None)

    def test_anonymous_user_passes(self):
        with self.assertNumQueries(0):
            self.assertIs(self._check(AnonymousUser()), True)

    def test_user_without_an_organization_passes(self):
        superuser = UserFactory.build(organization=None)

        with self.assertNumQueries(0):
            self.assertIs(self._check(superuser), True)

    def test_user_with_an_active_subscription_passes(self):
        user = UserFactory()
        StripeSubscriptionFactory(customer__subscriber=user.organization)

        with self.assertNumQueries(2):
            self.assertIs(self._check(user), True)

    def test_user_without_an_active_subscription_raises_402(self):
        user = UserFactory()

        with self.assertNumQueries(1), self.assertRaises(SubscriptionRequired):
            self._check(user)


class HasActiveSubscriptionEndpointTests(APITestCase):
    """End to end through ``invitation_list_create``, which carries
    ``HasActiveSubscription`` after ``IsOrganizationAdmin``."""

    def setUp(self):
        self.url = reverse("invitation_list_create")

    def test_active_subscription_passes_through(self):
        admin = AdminUserFactory()
        StripeSubscriptionFactory(customer__subscriber=admin.organization)
        self.client.force_authenticate(admin)

        with self.assertNumQueries(3):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_missing_subscription_is_blocked_with_402(self):
        self.client.force_authenticate(AdminUserFactory())

        with self.assertNumQueries(1):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(
            response.json(),
            {
                "detail": SubscriptionRequired.default_detail,
                "code": SubscriptionRequired.default_code,
            },
        )

    def test_expired_subscription_is_blocked_with_402(self):
        admin = AdminUserFactory()
        StripeSubscriptionFactory(
            customer__subscriber=admin.organization, status="canceled"
        )
        self.client.force_authenticate(admin)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_unauthenticated_request_is_not_subscription_gated(self):
        with self.assertNumQueries(0):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_admin_is_denied_before_the_subscription_check(self):
        self.client.force_authenticate(UserFactory())

        with self.assertNumQueries(0):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_allow_any_endpoint_is_never_gated(self):
        self.client.force_authenticate(AdminUserFactory())

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("auth_password_reset"), {"email": "nobody@example.com"}
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)


def _sign_webhook_payload(payload, secret):
    """Build a real ``Stripe-Signature`` header for a webhook body, using
    stripe's own test-signing helper - no cryptography is mocked here."""
    body = json.dumps(payload)
    header = stripe.WebhookSignature.generate_signature_header(
        payload=body, secret=secret
    )
    return body, header


class StripeWebhookEndpointTests(APITestCase):
    """The dj-stripe webhook is mounted and CSRF-exempt."""

    def setUp(self):
        self.endpoint = WebhookEndpointFactory()
        self.url = reverse(
            "djstripe:djstripe_webhook_by_uuid",
            kwargs={"uuid": str(self.endpoint.djstripe_uuid)},
        )

    def test_valid_signed_event_syncs_the_local_subscription(self):
        admin = AdminUserFactory()
        StripeCustomerFactory(subscriber=admin.organization, id="cus_test_webhook")
        subscription_object = {
            "id": "sub_test_webhook",
            "object": "subscription",
            "customer": "cus_test_webhook",
            "status": "active",
            "items": {
                "object": "list",
                "data": [],
                "has_more": False,
                "total_count": 0,
                "url": "/v1/subscription_items",
            },
        }
        body, signature = _sign_webhook_payload(
            {
                "id": "evt_test_webhook",
                "object": "event",
                "api_version": "2020-08-27",
                "livemode": False,
                "type": "customer.subscription.updated",
                "data": {"object": subscription_object},
            },
            self.endpoint.secret,
        )
        # dj-stripe's event handler re-fetches the canonical object from
        # Stripe rather than trusting the webhook payload - the one genuine
        # outbound API call in this flow, and the only thing mocked here.
        remote_subscription = stripe.Subscription.construct_from(
            subscription_object, "sk_test_dummy"
        )

        with (
            patch(
                "djstripe.models.Account.get_or_retrieve_for_api_key",
                return_value=None,
            ),
            patch("stripe.Subscription.retrieve", return_value=remote_subscription),
            self.assertNumQueries(17),
        ):
            response = self.client.post(
                self.url,
                data=body,
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE=signature,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(admin.organization.active_subscription)

    def test_endpoint_rejects_an_unsigned_payload(self):
        with self.assertNumQueries(0):
            response = self.client.post(
                self.url, data="{}", content_type="application/json"
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signed_payload_for_an_unknown_endpoint_uuid_is_404(self):
        unknown_url = reverse(
            "djstripe:djstripe_webhook_by_uuid",
            kwargs={"uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6"},
        )

        with self.assertNumQueries(1):
            response = self.client.post(
                unknown_url,
                data="{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=1,v1=deadbeef",
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
