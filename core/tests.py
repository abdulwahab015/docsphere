import json
import logging
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.logging.formatters import JSONFormatter
from core.middleware.logging import _redact
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
