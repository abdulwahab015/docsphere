import json
import logging
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse
from drf_spectacular.generators import SchemaGenerator
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.logging.formatters import JSONFormatter
from core.middleware.logging import _redact
from core.middleware.subscription_gating import (
    SUBSCRIPTION_REQUIRED_CODE,
    SUBSCRIPTION_REQUIRED_DETAIL,
)
from core.schema import add_subscription_gate_responses
from organizations.factories import OrganizationFactory, StripeSubscriptionFactory
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


class DefaultPaginationTests(APITestCase):
    def setUp(self):
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


def _bearer(user):
    """Build an ``Authorization`` header value. Writes an OutstandingToken row,
    so call it in arrange, never inside an ``assertNumQueries`` block."""
    return f"Bearer {RefreshToken.for_user(user).access_token}"


class SubscriptionGatingMiddlewareTests(APITestCase):
    """``/api/v1/users/invitations/`` (admin-only list) stands in for any
    non-exempt authenticated endpoint here."""

    def setUp(self):
        self.organization = OrganizationFactory()
        self.admin = AdminUserFactory(organization=self.organization)
        self.admin_auth = _bearer(self.admin)
        self.gated_url = reverse("invitation_list_create")

    def test_active_subscription_passes_through(self):
        StripeSubscriptionFactory(
            customer__subscriber=self.organization, status="active"
        )

        with self.assertNumQueries(7):
            response = self.client.get(
                self.gated_url, HTTP_AUTHORIZATION=self.admin_auth
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_missing_subscription_is_blocked_with_402(self):
        with self.assertNumQueries(3):
            response = self.client.get(
                self.gated_url, HTTP_AUTHORIZATION=self.admin_auth
            )

        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(
            response.json(),
            {
                "detail": SUBSCRIPTION_REQUIRED_DETAIL,
                "code": SUBSCRIPTION_REQUIRED_CODE,
            },
        )

    def test_expired_subscription_is_blocked_with_402(self):
        StripeSubscriptionFactory(
            customer__subscriber=self.organization, status="canceled"
        )

        with self.assertNumQueries(4):
            response = self.client.get(
                self.gated_url, HTTP_AUTHORIZATION=self.admin_auth
            )

        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_superuser_without_organization_bypasses_the_gate(self):
        superuser = UserFactory(organization=None, is_staff=True, is_superuser=True)
        superuser_auth = _bearer(superuser)

        with self.assertNumQueries(2):
            response = self.client.get(
                self.gated_url, HTTP_AUTHORIZATION=superuser_auth
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_login_is_not_gated(self):
        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("auth_login"),
                {"email": "nobody@example.com", "password": "wrong"},
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_exempt_password_reset_passes_through_without_a_subscription(self):
        with self.assertNumQueries(2):
            response = self.client.post(
                reverse("auth_password_reset"),
                {"email": "nobody@example.com"},
                HTTP_AUTHORIZATION=self.admin_auth,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_exempt_invitation_accept_passes_through_without_a_subscription(self):
        with self.assertNumQueries(2):
            response = self.client.post(
                reverse("invitation_accept"),
                {"token": "does-not-exist", "password": "irrelevant"},
                HTTP_AUTHORIZATION=self.admin_auth,
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request_to_a_gated_endpoint_is_not_gated(self):
        with self.assertNumQueries(0):
            response = self.client.get(self.gated_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_malformed_bearer_token_is_not_gated(self):
        with self.assertNumQueries(0):
            response = self.client.get(
                self.gated_url, HTTP_AUTHORIZATION="Bearer not-a-real-token"
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unroutable_path_is_left_to_the_view_layer(self):
        with self.assertNumQueries(0):
            response = self.client.get(
                "/api/v1/does-not-exist/", HTTP_AUTHORIZATION=self.admin_auth
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_session_authenticated_user_without_a_subscription_is_blocked(self):
        self.client.force_login(self.admin)

        with self.assertNumQueries(4):
            response = self.client.get(self.gated_url)

        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)


class StripeWebhookEndpointTests(APITestCase):
    """The dj-stripe webhook is mounted, CSRF-exempt, and never subscription-gated
    (Stripe authenticates with a signature header, not a JWT). Signature
    verification itself is dj-stripe's concern and isn't re-tested here."""

    def setUp(self):
        self.url = reverse(
            "djstripe:djstripe_webhook_by_uuid",
            kwargs={"uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6"},
        )

    def test_endpoint_is_routed_and_rejects_an_unsigned_payload(self):
        with self.assertNumQueries(0):
            response = self.client.post(
                self.url, data="{}", content_type="application/json"
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_not_subscription_gated_even_with_a_bearer_token_for_an_unpaid_org(self):
        admin = AdminUserFactory(organization=OrganizationFactory())
        admin_auth = _bearer(admin)

        with self.assertNumQueries(0):
            response = self.client.post(
                self.url,
                data="{}",
                content_type="application/json",
                HTTP_AUTHORIZATION=admin_auth,
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signed_payload_for_an_unknown_endpoint_uuid_is_404(self):
        with self.assertNumQueries(1):
            response = self.client.post(
                self.url,
                data="{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=1,v1=deadbeef",
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class SubscriptionGate402SchemaTests(SimpleTestCase):
    """The postprocessing hook documents the middleware-level 402 on every
    non-exempt operation and leaves the allowlisted ones alone."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema = SchemaGenerator().get_schema(request=None, public=True)

    def _responses(self, path, method):
        return self.schema["paths"][path][method]["responses"]

    def test_non_exempt_operation_documents_the_402(self):
        responses = self._responses("/api/v1/users/invitations/", "get")

        self.assertIn("402", responses)
        schema = responses["402"]["content"]["application/json"]["schema"]
        self.assertEqual(schema["properties"]["detail"]["type"], "string")
        self.assertEqual(
            schema["properties"]["code"]["enum"], [SUBSCRIPTION_REQUIRED_CODE]
        )

    def test_exempt_auth_operation_is_left_alone(self):
        self.assertNotIn("402", self._responses("/api/v1/users/auth/login/", "post"))

    def test_exempt_invitation_accept_is_left_alone(self):
        self.assertNotIn(
            "402", self._responses("/api/v1/users/invitations/accept/", "post")
        )

    def test_operational_healthz_is_left_alone(self):
        self.assertNotIn("402", self._responses("/healthz/", "get"))

    def test_hook_skips_non_method_keys_and_unresolvable_paths(self):
        result = {
            "paths": {
                "/api/v1/users/invitations/": {
                    "parameters": [{"name": "x", "in": "query"}],
                    "get": {"responses": {"200": {"description": "ok"}}},
                },
                "/not/a/real/route/": {
                    "get": {"responses": {"200": {"description": "ok"}}},
                },
            }
        }

        add_subscription_gate_responses(result, None, None, True)

        invitations = result["paths"]["/api/v1/users/invitations/"]
        self.assertEqual(invitations["parameters"], [{"name": "x", "in": "query"}])
        self.assertIn("402", invitations["get"]["responses"])
        self.assertNotIn(
            "402", result["paths"]["/not/a/real/route/"]["get"]["responses"]
        )
