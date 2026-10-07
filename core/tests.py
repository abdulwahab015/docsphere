import json
import logging
import smtplib
from unittest.mock import PropertyMock, patch

import sentry_sdk
import stripe
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.module_loading import autodiscover_modules
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from sentry_sdk.transport import Transport

from core.celery import app as celery_app
from core.email import EMAIL_MAX_RETRIES
from core.error_tracking import init_error_tracking, scrub_event
from core.logging.formatters import JSONFormatter
from core.middleware.logging import _redact
from core.permissions import HasActiveSubscription, SubscriptionRequired
from organizations.factories import (
    StripeCustomerFactory,
    StripeSubscriptionFactory,
    WebhookEndpointFactory,
)
from organizations.models import Organization
from projects.tasks import (
    send_access_request_approved_email_task,
    send_access_request_created_email_task,
    send_access_request_denied_email_task,
    send_document_shared_email_task,
    send_project_shared_email_task,
)
from subscriptions.tasks import send_expiry_reminder_email_task
from users.factories import AdminUserFactory, InvitationFactory, UserFactory
from users.tasks import send_invitation_email_task, send_password_reset_email_task


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
            self.assertNumQueries(3),
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

        self.assertEqual(captured.records[0].client_ip, "10.0.0.1")


class AssumeActiveSubscription:
    """Test mixin that makes ``Organization.active_subscription`` truthy for the
    duration of each test, so ``HasActiveSubscription`` passes without any
    dj-stripe rows. Use it where a paid organization is a precondition rather
    than the thing under test."""

    def setUp(self):
        super().setUp()
        patcher = patch.object(
            Organization,
            "active_subscription",
            new_callable=PropertyMock,
            return_value=True,
        )
        patcher.start()
        self.addCleanup(patcher.stop)


class DefaultPaginationTests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.admin = AdminUserFactory()
        InvitationFactory(organization=self.admin.organization, invited_by=self.admin)

    def test_list_endpoints_return_the_paginated_envelope(self):
        self.client.force_authenticate(self.admin)

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

    def test_user_whose_renewal_payment_is_being_retried_passes(self):
        user = UserFactory()
        StripeSubscriptionFactory(
            customer__subscriber=user.organization, status="past_due"
        )

        with self.assertNumQueries(2):
            self.assertIs(self._check(user), True)

    def test_user_without_an_active_subscription_raises_402(self):
        user = UserFactory()

        with self.assertNumQueries(1), self.assertRaises(SubscriptionRequired):
            self._check(user)

    def test_user_whose_subscription_stripe_gave_up_on_raises_402(self):
        for status_name in ("unpaid", "canceled", "incomplete_expired"):
            with self.subTest(status_name):
                user = UserFactory()
                StripeSubscriptionFactory(
                    customer__subscriber=user.organization, status=status_name
                )

                with self.assertNumQueries(2), self.assertRaises(SubscriptionRequired):
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


EAGER_PROPAGATES_SETTING = "CELERY_TASK_EAGER_PROPAGATES"


class CeleryBeatScheduleTests(SimpleTestCase):
    def test_every_scheduled_task_is_registered_with_the_celery_app(self):
        # What the Celery app's autodiscovery does when a worker or beat starts.
        autodiscover_modules("tasks")

        for entry_name, entry in settings.CELERY_BEAT_SCHEDULE.items():
            with self.subTest(entry_name):
                self.assertIn(entry["task"], celery_app.tasks)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class EmailTaskRetryTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        # Eager, but without the test settings' CELERY_TASK_EAGER_PROPAGATES:
        # with it, Celery raises its internal Retry exception instead of
        # running the retry. The Celery app has already read its settings, so
        # it's changed on the app itself; the outcome is read from the result.
        propagates = celery_app.conf[EAGER_PROPAGATES_SETTING]
        celery_app.conf[EAGER_PROPAGATES_SETTING] = False
        self.addCleanup(
            celery_app.conf.__setitem__, EAGER_PROPAGATES_SETTING, propagates
        )

    @patch("core.email.send_mail")
    def test_a_failed_send_is_retried_until_it_goes_through(self, mock_send_mail):
        mock_send_mail.side_effect = [
            smtplib.SMTPServerDisconnected("Connection unexpectedly closed"),
            None,
        ]

        with self.assertNumQueries(2):
            result = send_password_reset_email_task.delay(self.user.pk)

        self.assertTrue(result.successful())
        self.assertEqual(mock_send_mail.call_count, 2)

    @patch("core.email.send_mail")
    def test_gives_up_after_the_retry_limit(self, mock_send_mail):
        mock_send_mail.side_effect = ConnectionRefusedError()

        with self.assertNumQueries(EMAIL_MAX_RETRIES + 1):
            result = send_password_reset_email_task.delay(self.user.pk)

        self.assertIsInstance(result.result, ConnectionRefusedError)
        self.assertEqual(mock_send_mail.call_count, EMAIL_MAX_RETRIES + 1)

    @patch("core.email.send_mail")
    def test_an_error_that_retrying_cannot_fix_fails_at_once(self, mock_send_mail):
        mock_send_mail.side_effect = ValueError("Invalid address")

        with self.assertNumQueries(1):
            result = send_password_reset_email_task.delay(self.user.pk)

        self.assertIsInstance(result.result, ValueError)
        mock_send_mail.assert_called_once()

    def test_every_email_task_retries_failed_sends(self):
        email_tasks = [
            send_invitation_email_task,
            send_password_reset_email_task,
            send_project_shared_email_task,
            send_document_shared_email_task,
            send_access_request_created_email_task,
            send_access_request_approved_email_task,
            send_access_request_denied_email_task,
            send_expiry_reminder_email_task,
        ]

        for task in email_tasks:
            with self.subTest(task.name):
                self.assertEqual(task.autoretry_for, (OSError,))
                self.assertEqual(task.max_retries, EMAIL_MAX_RETRIES)


DSN = "https://public@errors.example.com/1"


class ErrorTrackingSetupTests(SimpleTestCase):
    @override_settings(SENTRY_DSN="")
    @patch("core.error_tracking.sentry_sdk.init")
    def test_stays_off_without_a_dsn(self, mock_init):
        self.assertIs(init_error_tracking(), False)

        mock_init.assert_not_called()

    @override_settings(
        SENTRY_DSN=DSN, SENTRY_ENVIRONMENT="staging", SENTRY_RELEASE="abc123"
    )
    @patch("core.error_tracking.sentry_sdk.init")
    def test_starts_with_a_dsn_without_sending_personal_data(self, mock_init):
        self.assertIs(init_error_tracking(), True)

        options = mock_init.call_args.kwargs
        self.assertEqual(options["dsn"], DSN)
        self.assertEqual(options["environment"], "staging")
        self.assertEqual(options["release"], "abc123")
        self.assertIs(options["send_default_pii"], False)
        self.assertIs(options["include_local_variables"], False)
        self.assertEqual(options["max_request_body_size"], "never")
        self.assertIs(options["before_send"], scrub_event)

    def test_scrubbing_keeps_only_the_request_method_path_and_user_id(self):
        event = {
            "request": {
                "method": "POST",
                "url": "https://docsphere.example.com/api/v1/documents/",
                "query_string": "search=secret",
                "headers": {"Authorization": "Bearer abc"},
                "cookies": {"refresh_token": "xyz"},
                "data": {"content": "Private notes"},
                "env": {"REMOTE_ADDR": "203.0.113.7"},
            },
            "user": {
                "id": "7",
                "email": "ada@example.com",
                "ip_address": "203.0.113.7",
            },
        }

        self.assertEqual(
            scrub_event(event, hint={}),
            {
                "request": {
                    "method": "POST",
                    "url": "https://docsphere.example.com/api/v1/documents/",
                },
                "user": {"id": "7"},
            },
        )


class ErrorTrackingScrubbingTests(SimpleTestCase):
    def test_an_error_outside_any_request_passes_through_unchanged(self):
        # e.g. a Celery task's: no request, and nobody signed in.
        event = {"exception": {"values": [{"type": "OSError"}]}}

        self.assertEqual(scrub_event(dict(event), hint={}), event)


class _CapturingTransport(Transport):
    """Keeps the events the SDK would have sent."""

    def __init__(self, options=None):
        super().__init__(options)
        self.events = []

    def capture_envelope(self, envelope):
        event = envelope.get_event()
        if event:
            self.events.append(event)


@override_settings(SENTRY_DSN=DSN)
class ErrorReportTests(AssumeActiveSubscription, APITestCase):
    """A real failing request, reported through the real SDK."""

    def setUp(self):
        super().setUp()
        self.transport = _CapturingTransport()
        start = sentry_sdk.init
        with patch(
            "core.error_tracking.sentry_sdk.init",
            side_effect=lambda **options: start(transport=self.transport, **options),
        ):
            init_error_tracking()
        self.addCleanup(lambda: sentry_sdk.get_client().close())
        self.client.raise_request_exception = False

    @patch(
        "projects.api.v1.views.ProjectListCreateAPIView.perform_create",
        side_effect=RuntimeError("Something broke"),
    )
    def test_says_whose_request_failed_by_id_and_nothing_more(self, _mock_create):
        admin = AdminUserFactory()
        token = str(RefreshToken.for_user(admin).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        with self.assertNumQueries(3):
            response = self.client.post(
                f"{reverse('project_list_create')}?from=secret-search-term",
                {"name": "Secret plans", "description": "Private notes"},
                format="json",
            )
        sentry_sdk.flush()

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        (event,) = self.transport.events
        self.assertEqual(event["exception"]["values"][-1]["type"], "RuntimeError")
        self.assertEqual(event["user"], {"id": str(admin.pk)})
        self.assertEqual(event["tags"]["organization_id"], str(admin.organization_id))
        # Under gunicorn the method and URL are there too: the SDK adds them as
        # the request passes Django's WSGI handler, which the test client skips.
        self.assertLessEqual(set(event["request"]), {"method", "url"})
        reported = json.dumps(event)
        for private in (
            token,
            admin.email,
            "Secret plans",
            "Private notes",
            "secret-search-term",
        ):
            self.assertNotIn(private, reported)
