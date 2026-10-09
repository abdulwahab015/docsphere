import contextlib
import threading
import time
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import (
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    override_settings,
    skipUnlessDBFeature,
)
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from openpyxl import Workbook
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from audit.choices import AuditVerb
from audit.models import AuditEvent
from core.tests import AssumeActiveSubscription
from notifications.factories import NotificationFactory
from organizations.factories import OrganizationFactory, StripeSubscriptionFactory
from organizations.models import Organization
from projects.choices import AccessLevel, AccessRequestStatus
from projects.factories import (
    DocumentAccessRequestFactory,
    DocumentFactory,
    DocumentPermissionFactory,
)
from projects.models import DocumentAccessRequest, DocumentPermission
from users import services as user_services
from users.api.v1 import views as user_views
from users.choices import InvitationStatus, OrganizationRole
from users.constants import MAX_BULK_INVITE_ROWS, MAX_NAME_LENGTH
from users.email_links import (
    INVALID_EMAIL_LINK_MESSAGE,
    make_email_change_token,
    make_verification_token,
)
from users.factories import (
    DEFAULT_TEST_PASSWORD,
    AdminUserFactory,
    InvitationFactory,
    UserFactory,
)
from users.models import Invitation
from users.password_validation import ComplexityValidator, MaximumLengthValidator
from users.services import (
    EMAIL_IN_USE_MESSAGE,
    LAST_ADMIN_LEAVING_MESSAGE,
    NO_LONGER_ADMIN_MESSAGE,
    sole_owner_message,
)
from users.tasks import remove_unverified_accounts_task

User = get_user_model()

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def lapse_verification(user):
    """Backdates an unverified signup past ``EMAIL_LINK_EXPIRY``, after which
    it no longer holds its address."""
    User.objects.filter(pk=user.pk).update(
        created=timezone.now() - settings.EMAIL_LINK_EXPIRY - timedelta(minutes=1)
    )


def after_links_expire():
    """Moves the clock the email links are signed with past their expiry."""
    return patch(
        "django.core.signing.time.time",
        return_value=time.time() + settings.EMAIL_LINK_EXPIRY.total_seconds() + 1,
    )


def build_xlsx_upload(values, filename="invitees.xlsx"):
    """Build an in-memory single-column .xlsx upload from a list of cell values."""
    workbook = Workbook()
    worksheet = workbook.active
    for value in values:
        worksheet.append([value])

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    return SimpleUploadedFile(filename, buffer.read(), content_type=XLSX_CONTENT_TYPE)


class JWTAuthTests(APITestCase):
    def setUp(self):
        self.password = "S0me-Strong-Pass!"
        self.user = UserFactory(
            email="member@example.com", password=self.password, organization=None
        )

    def test_login_succeeds_with_correct_credentials(self):
        with self.assertNumQueries(3):
            response = self.client.post(
                reverse("auth_login"),
                {"email": self.user.email, "password": self.password},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_email_is_stored_lowercase_and_login_is_case_insensitive(self):
        user = UserFactory(
            email="Mixed.Case@Example.com", password=self.password, organization=None
        )
        self.assertEqual(user.email, "mixed.case@example.com")

        with self.assertNumQueries(3):
            response = self.client.post(
                reverse("auth_login"),
                {"email": "MIXED.CASE@EXAMPLE.COM", "password": self.password},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_fails_with_wrong_password(self):
        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("auth_login"),
                {"email": self.user.email, "password": "wrong-password"},
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_rejects_an_oversized_password_without_hashing_it(self):
        with self.assertNumQueries(0):
            response = self.client.post(
                reverse("auth_login"),
                {"email": self.user.email, "password": "x" * 5000},
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_is_rate_limited(self):
        cache.clear()
        with patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"login": "1/min"}):
            with self.assertNumQueries(1):
                first = self.client.post(
                    reverse("auth_login"),
                    {"email": self.user.email, "password": "wrong-password"},
                )
            self.assertEqual(first.status_code, status.HTTP_401_UNAUTHORIZED)

            with self.assertNumQueries(0):
                second = self.client.post(
                    reverse("auth_login"),
                    {"email": self.user.email, "password": self.password},
                )
            self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_refresh_returns_new_access_token(self):
        with self.assertNumQueries(3):
            login_response = self.client.post(
                reverse("auth_login"),
                {"email": self.user.email, "password": self.password},
            )
        refresh_token = login_response.data["refresh"]

        with self.assertNumQueries(13):
            response = self.client.post(
                reverse("auth_refresh"), {"refresh": refresh_token}
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_logout_blacklists_refresh_token(self):
        with self.assertNumQueries(3):
            login_response = self.client.post(
                reverse("auth_login"),
                {"email": self.user.email, "password": self.password},
            )
        refresh_token = login_response.data["refresh"]

        with self.assertNumQueries(7):
            logout_response = self.client.post(
                reverse("auth_logout"), {"refresh": refresh_token}
            )
        self.assertEqual(logout_response.status_code, status.HTTP_205_RESET_CONTENT)

        with self.assertNumQueries(1):
            reuse_response = self.client.post(
                reverse("auth_refresh"), {"refresh": refresh_token}
            )
        self.assertEqual(reuse_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_a_refresh_token(self):
        with self.assertNumQueries(0):
            response = self.client.post(reverse("auth_logout"), {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_rejects_a_malformed_refresh_token(self):
        with self.assertNumQueries(0):
            response = self.client.post(
                reverse("auth_logout"), {"refresh": "not-a-real-token"}
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class RefreshCookieTests(APITestCase):
    """The refresh token also travels as an HttpOnly cookie scoped to the auth
    endpoints, which refresh and logout fall back to when the body has none."""

    def setUp(self):
        self.password = "S0me-Strong-Pass!"
        self.user = UserFactory(password=self.password)
        self.cookie_name = settings.REFRESH_COOKIE_NAME

    def test_login_sets_an_httponly_refresh_cookie_scoped_to_auth(self):
        with self.assertNumQueries(3):
            response = self.client.post(
                reverse("auth_login"),
                {"email": self.user.email, "password": self.password},
            )

        cookie = response.cookies[self.cookie_name]
        self.assertEqual(cookie.value, response.data["refresh"])
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["path"], settings.REFRESH_COOKIE_PATH)
        self.assertEqual(cookie["samesite"], settings.REFRESH_COOKIE_SAMESITE)

    def test_refresh_with_only_the_cookie_rotates_it(self):
        old_refresh = str(RefreshToken.for_user(self.user))
        self.client.cookies[self.cookie_name] = old_refresh

        with self.assertNumQueries(13):
            response = self.client.post(reverse("auth_refresh"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        new_cookie = response.cookies[self.cookie_name].value
        self.assertEqual(new_cookie, response.data["refresh"])
        self.assertNotEqual(new_cookie, old_refresh)

    def test_refresh_token_in_the_body_still_works_and_wins_over_the_cookie(self):
        self.client.cookies[self.cookie_name] = "not-a-token"
        refresh = str(RefreshToken.for_user(self.user))

        with self.assertNumQueries(13):
            response = self.client.post(reverse("auth_refresh"), {"refresh": refresh})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_refresh_without_a_body_or_cookie_is_rejected(self):
        with self.assertNumQueries(0):
            response = self.client.post(reverse("auth_refresh"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_with_only_the_cookie_blacklists_it_and_clears_the_cookie(self):
        refresh = str(RefreshToken.for_user(self.user))
        self.client.cookies[self.cookie_name] = refresh

        with self.assertNumQueries(7):
            response = self.client.post(reverse("auth_logout"))

        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)
        self.assertEqual(response.cookies[self.cookie_name].value, "")
        with self.assertNumQueries(1):
            refresh_response = self.client.post(
                reverse("auth_refresh"), {"refresh": refresh}
            )
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordResetTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = UserFactory(
            email="member@example.com", password="Old-Pass-123!", organization=None
        )

    @patch("core.email.send_mail")
    def test_password_reset_request_sends_email(self, mock_send_mail):
        with self.assertNumQueries(3):
            response = self.client.post(
                reverse("auth_password_reset"), {"email": self.user.email}
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_mail.assert_called_once()

    @patch("core.email.send_mail")
    def test_a_deactivated_user_is_sent_no_reset_link(self, mock_send_mail):
        # They couldn't log in with a new password anyway.
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("auth_password_reset"), {"email": self.user.email}
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_mail.assert_not_called()

    @patch("core.email.send_mail")
    def test_password_reset_request_with_unknown_email_still_returns_200(
        self, mock_send_mail
    ):
        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("auth_password_reset"), {"email": "nobody@example.com"}
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_mail.assert_not_called()

    @patch("core.email.send_mail")
    def test_password_reset_request_is_throttled_after_limit(self, mock_send_mail):
        with patch.object(
            ScopedRateThrottle, "THROTTLE_RATES", {"password_reset": "2/min"}
        ):
            for _ in range(2):
                with self.assertNumQueries(3):
                    response = self.client.post(
                        reverse("auth_password_reset"), {"email": self.user.email}
                    )
                self.assertEqual(response.status_code, status.HTTP_200_OK)

            with self.assertNumQueries(0):
                response = self.client.post(
                    reverse("auth_password_reset"), {"email": self.user.email}
                )
            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_password_reset_confirm_changes_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        new_password = "New-Strong-Pass!456"

        with self.assertNumQueries(5):
            response = self.client.post(
                reverse("auth_password_reset_confirm"),
                {"uid": uid, "token": token, "new_password": new_password},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    def test_password_reset_confirm_revokes_existing_refresh_tokens(self):
        with self.assertNumQueries(3):
            login = self.client.post(
                reverse("auth_login"),
                {"email": self.user.email, "password": "Old-Pass-123!"},
            )
        old_refresh = login.data["refresh"]

        # The login recorded last_login, which reset tokens include.
        self.user.refresh_from_db()
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        with self.assertNumQueries(9):
            self.client.post(
                reverse("auth_password_reset_confirm"),
                {"uid": uid, "token": token, "new_password": "New-Strong-Pass!456"},
            )

        with self.assertNumQueries(1):
            reuse = self.client.post(reverse("auth_refresh"), {"refresh": old_refresh})
        self.assertEqual(reuse.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_reset_link_sent_before_a_login_no_longer_works(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        self.client.post(
            reverse("auth_login"),
            {"email": self.user.email, "password": "Old-Pass-123!"},
        )

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("auth_password_reset_confirm"),
                {"uid": uid, "token": token, "new_password": "New-Strong-Pass!456"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)
        self.assertTrue(self.user.check_password("Old-Pass-123!"))

    def test_password_reset_confirm_fails_with_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("auth_password_reset_confirm"),
                {
                    "uid": uid,
                    "token": "invalid-token",
                    "new_password": "New-Strong-Pass!456",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_confirm_fails_for_nonexistent_user(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk + 1000))
        token = default_token_generator.make_token(self.user)

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("auth_password_reset_confirm"),
                {
                    "uid": uid,
                    "token": token,
                    "new_password": "New-Strong-Pass!456",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_confirm_fails_with_a_malformed_uid(self):
        with self.assertNumQueries(0):
            response = self.client.post(
                reverse("auth_password_reset_confirm"),
                {
                    "uid": "@@@not-base64@@@",
                    "token": "x",
                    "new_password": "New-Strong-Pass!456",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_confirm_reports_a_weak_password_on_its_field(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("auth_password_reset_confirm"),
                {"uid": uid, "token": token, "new_password": "alllowercase1"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)
        self.assertNotIn("non_field_errors", response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Old-Pass-123!"))


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class PasswordChangeTests(APITestCase):
    def setUp(self):
        self.password = "S0me-Strong-Pass!"
        self.new_password = "An0ther-Strong-Pass!"
        self.user = UserFactory(password=self.password)
        self.url = reverse("user_password_change")

    def test_changes_password_revokes_old_sessions_and_returns_a_new_pair(self):
        old_refresh = str(RefreshToken.for_user(self.user))
        self.client.force_authenticate(self.user)

        with self.assertNumQueries(9):
            response = self.client.post(
                self.url,
                {"current_password": self.password, "new_password": self.new_password},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertEqual(
            response.cookies[settings.REFRESH_COOKIE_NAME].value,
            response.data["refresh"],
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.client.force_authenticate(None)
        with self.assertNumQueries(1):
            stale = self.client.post(reverse("auth_refresh"), {"refresh": old_refresh})
        self.assertEqual(stale.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_a_wrong_current_password(self):
        self.client.force_authenticate(self.user)

        with self.assertNumQueries(0):
            response = self.client.post(
                self.url,
                {"current_password": "Wr0ng-Pass!", "new_password": self.new_password},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_password", response.data)

    def test_rejects_a_new_password_that_fails_the_policy(self):
        self.client.force_authenticate(self.user)

        with self.assertNumQueries(0):
            response = self.client.post(
                self.url,
                {"current_password": self.password, "new_password": "short"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)
        self.assertNotIn("non_field_errors", response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_anonymous_request_is_rejected(self):
        with self.assertNumQueries(0):
            response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_is_rate_limited(self):
        cache.clear()
        self.client.force_authenticate(self.user)
        payload = {"current_password": "Wr0ng-Pass!", "new_password": "x"}

        with patch.object(
            ScopedRateThrottle, "THROTTLE_RATES", {"password_change": "1/min"}
        ):
            with self.assertNumQueries(0):
                self.client.post(self.url, payload)
            with self.assertNumQueries(0):
                response = self.client.post(self.url, payload)

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class EmailVerificationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = AdminUserFactory(email="admin@acme.test", email_verified_at=None)
        self.verify_url = reverse("auth_verify_email")
        self.resend_url = reverse("user_verification_email_resend")

    def test_the_emailed_link_verifies_the_address(self):
        token = make_verification_token(self.user)

        with self.assertNumQueries(2):
            response = self.client.post(self.verify_url, {"token": token})

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    def test_following_the_link_again_changes_nothing(self):
        token = make_verification_token(self.user)
        self.client.post(self.verify_url, {"token": token})
        self.user.refresh_from_db()
        verified_at = self.user.email_verified_at

        with self.assertNumQueries(1):
            response = self.client.post(self.verify_url, {"token": token})

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email_verified_at, verified_at)

    def test_an_expired_link_is_refused(self):
        token = make_verification_token(self.user)

        with after_links_expire(), self.assertNumQueries(0):
            response = self.client.post(self.verify_url, {"token": token})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["token"], [INVALID_EMAIL_LINK_MESSAGE])
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_a_forged_link_is_refused(self):
        token = make_verification_token(self.user)
        forged = token[:-1] + ("A" if token[-1] != "A" else "B")

        with self.assertNumQueries(0):
            response = self.client.post(self.verify_url, {"token": forged})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["token"], [INVALID_EMAIL_LINK_MESSAGE])

    def test_a_link_for_another_address_of_the_account_is_refused(self):
        token = make_verification_token(self.user)
        User.objects.filter(pk=self.user.pk).update(email="moved@acme.test")

        with self.assertNumQueries(1):
            response = self.client.post(self.verify_url, {"token": token})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_an_email_change_link_is_refused(self):
        # An email-change link must not double as a verification link.
        token = make_email_change_token(self.user, "new@acme.test")

        with self.assertNumQueries(0):
            response = self.client.post(self.verify_url, {"token": token})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_emails_a_new_link(self):
        self.client.force_authenticate(self.user)

        with self.assertNumQueries(1):
            response = self.client.post(self.resend_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@acme.test"])
        self.assertIn(
            f"{settings.FRONTEND_URL}/verify-email?token=", mail.outbox[0].body
        )

    def test_resend_is_refused_once_verified(self):
        verified = UserFactory()
        self.client.force_authenticate(verified)

        with self.assertNumQueries(0):
            response = self.client.post(self.resend_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_needs_a_signed_in_user(self):
        with self.assertNumQueries(0):
            response = self.client.post(self.resend_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_resend_is_rate_limited(self):
        self.client.force_authenticate(self.user)

        with patch.object(
            ScopedRateThrottle, "THROTTLE_RATES", {"email_verification": "1/min"}
        ):
            with self.assertNumQueries(1):
                self.client.post(self.resend_url)
            with self.assertNumQueries(0):
                response = self.client.post(self.resend_url)

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(len(mail.outbox), 1)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class EmailChangeTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.password = "S0me-Strong-Pass!"
        self.user = UserFactory(email="old@acme.test", password=self.password)
        self.request_url = reverse("user_email_change")
        self.confirm_url = reverse("auth_confirm_email")

    def request_change(self, new_email, password=None):
        return self.client.post(
            self.request_url,
            {"new_email": new_email, "current_password": password or self.password},
        )

    def test_request_emails_a_link_to_the_new_address_and_changes_nothing_yet(self):
        self.client.force_authenticate(self.user)

        with self.assertNumQueries(3):
            response = self.request_change("New@Acme.test")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["New@Acme.test"])
        self.assertIn("old@acme.test", message.body)
        self.assertIn(f"{settings.FRONTEND_URL}/confirm-email?token=", message.body)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "old@acme.test")

    def test_confirming_moves_the_account_signs_out_everywhere_and_tells_the_old_address(
        self,
    ):
        old_refresh = str(RefreshToken.for_user(self.user))
        token = make_email_change_token(self.user, "new@acme.test")

        with self.assertNumQueries(12):
            response = self.client.post(self.confirm_url, {"token": token})

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@acme.test")
        self.assertTrue(self.user.email_verified)
        refreshed = self.client.post(reverse("auth_refresh"), {"refresh": old_refresh})
        self.assertEqual(refreshed.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["old@acme.test"])
        self.assertIn("new@acme.test", mail.outbox[0].body)

    def test_after_the_change_only_the_new_address_logs_in(self):
        token = make_email_change_token(self.user, "new@acme.test")
        self.client.post(self.confirm_url, {"token": token})
        login_url = reverse("auth_login")

        old = self.client.post(
            login_url, {"email": "old@acme.test", "password": self.password}
        )
        new = self.client.post(
            login_url, {"email": "new@acme.test", "password": self.password}
        )

        self.assertEqual(old.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(new.status_code, status.HTTP_200_OK)

    def test_confirming_takes_the_address_from_an_account_that_never_verified_it(self):
        squatter = AdminUserFactory(email="new@acme.test", email_verified_at=None)
        lapse_verification(squatter)
        token = make_email_change_token(self.user, "new@acme.test")

        response = self.client.post(self.confirm_url, {"token": token})

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Organization.objects.filter(pk=squatter.organization_id).exists()
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@acme.test")

    def test_request_refuses_a_wrong_current_password(self):
        self.client.force_authenticate(self.user)

        with self.assertNumQueries(2):
            response = self.request_change("new@acme.test", password="Wr0ng-Pass!")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_password", response.data)
        self.assertEqual(len(mail.outbox), 0)

    def test_request_refuses_the_current_address(self):
        self.client.force_authenticate(self.user)

        with self.assertNumQueries(0):
            response = self.request_change("OLD@acme.test")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["new_email"], ["This is already your email address."]
        )

    def test_request_refuses_an_address_another_account_holds(self):
        UserFactory(email="taken@acme.test", organization=None)
        self.client.force_authenticate(self.user)

        with self.assertNumQueries(1):
            response = self.request_change("taken@acme.test")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["new_email"], [EMAIL_IN_USE_MESSAGE])

    def test_request_refuses_an_address_with_a_pending_invitation(self):
        InvitationFactory(email="invited@acme.test")
        self.client.force_authenticate(self.user)

        with self.assertNumQueries(2):
            response = self.request_change("invited@acme.test")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["new_email"], [EMAIL_IN_USE_MESSAGE])

    def test_request_needs_a_verified_address(self):
        unverified = AdminUserFactory(email_verified_at=None)
        self.client.force_authenticate(unverified)

        with self.assertNumQueries(0):
            response = self.request_change("new@acme.test")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "email_unverified")

    def test_request_needs_a_signed_in_user(self):
        with self.assertNumQueries(0):
            response = self.request_change("new@acme.test")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_request_is_rate_limited(self):
        self.client.force_authenticate(self.user)

        with patch.object(
            ScopedRateThrottle, "THROTTLE_RATES", {"email_change": "1/min"}
        ):
            self.request_change("new@acme.test")
            with self.assertNumQueries(0):
                response = self.request_change("other@acme.test")

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_confirm_refuses_a_link_already_used(self):
        token = make_email_change_token(self.user, "new@acme.test")
        self.client.post(self.confirm_url, {"token": token})

        with self.assertNumQueries(1):
            response = self.client.post(self.confirm_url, {"token": token})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["token"], [INVALID_EMAIL_LINK_MESSAGE])

    def test_confirm_refuses_an_address_taken_since_the_link_was_sent(self):
        token = make_email_change_token(self.user, "new@acme.test")
        UserFactory(email="new@acme.test", organization=None)

        with self.assertNumQueries(5):
            response = self.client.post(self.confirm_url, {"token": token})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], EMAIL_IN_USE_MESSAGE)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "old@acme.test")
        self.assertEqual(len(mail.outbox), 0)

    def test_confirm_refuses_an_expired_link(self):
        token = make_email_change_token(self.user, "new@acme.test")

        with after_links_expire(), self.assertNumQueries(0):
            response = self.client.post(self.confirm_url, {"token": token})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "old@acme.test")

    def test_confirm_refuses_a_verification_link(self):
        token = make_verification_token(self.user)

        with self.assertNumQueries(0):
            response = self.client.post(self.confirm_url, {"token": token})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_refuses_a_deactivated_account(self):
        token = make_email_change_token(self.user, "new@acme.test")
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        with self.assertNumQueries(1):
            response = self.client.post(self.confirm_url, {"token": token})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EmailVerificationGateTests(APITestCase):
    """Until a new signup verifies their address, every endpoint refuses them
    except the few that let them verify, sign in and out, and see why."""

    # (URL name, method) pairs an unverified signup may still use.
    OPEN_TO_UNVERIFIED = frozenset(
        {
            ("auth_login", "post"),
            ("auth_refresh", "post"),
            ("auth_logout", "post"),
            ("auth_password_reset", "post"),
            ("auth_password_reset_confirm", "post"),
            ("auth_verify_email", "post"),
            ("auth_confirm_email", "post"),
            ("invitation_accept", "post"),
            ("organization_signup", "post"),
            ("user_me", "get"),
            ("user_verification_email_resend", "post"),
        }
    )

    def setUp(self):
        # An organization that hasn't subscribed yet, like every new signup:
        # the refusal must say "verify" before it says "pay".
        self.user = AdminUserFactory(email_verified_at=None)
        self.client.force_authenticate(self.user)

    def api_endpoints(self):
        """Every named API route, with a placeholder id in its URL, and the
        methods its view answers."""

        def walk(patterns, prefix):
            for pattern in patterns:
                route = prefix + str(pattern.pattern)
                if isinstance(pattern, URLResolver):
                    yield from walk(pattern.url_patterns, route)
                elif isinstance(pattern, URLPattern) and route.startswith("api/v1/"):
                    yield pattern

        for pattern in walk(get_resolver().url_patterns, ""):
            view_class = pattern.callback.view_class
            url = reverse(
                pattern.name,
                kwargs=dict.fromkeys(pattern.pattern.converters, 1),
            )
            for method in view_class.http_method_names:
                if method not in ("head", "options") and hasattr(view_class, method):
                    yield pattern.name, method, url

    def test_every_other_endpoint_refuses_an_unverified_signup(self):
        refused = []
        for name, method, url in self.api_endpoints():
            if (name, method) in self.OPEN_TO_UNVERIFIED:
                continue
            with self.subTest(endpoint=name, method=method):
                with self.assertNumQueries(0):
                    response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(response.data["code"], "email_unverified")
                refused.append(name)

        # The walk found the API: every app's endpoints were checked.
        self.assertIn("project_list_create", refused)
        self.assertIn("subscriptions_checkout", refused)
        self.assertIn("organization_profile", refused)

    def test_the_open_endpoints_exist(self):
        endpoints = {(name, method) for name, method, _ in self.api_endpoints()}

        self.assertLessEqual(self.OPEN_TO_UNVERIFIED, endpoints)


class InvitationTests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.org_a = OrganizationFactory(name="Org A")
        self.org_b = OrganizationFactory(name="Org B")

        self.admin_a = AdminUserFactory(
            email="admin-a@example.com", organization=self.org_a
        )
        self.member_a = UserFactory(
            email="member-a@example.com", organization=self.org_a
        )
        self.admin_b = AdminUserFactory(
            email="admin-b@example.com", organization=self.org_b
        )

    @patch("core.email.send_mail")
    def test_admin_can_create_invitation_for_own_organization(self, mock_send_mail):
        self.client.force_authenticate(self.admin_a)

        with self.assertNumQueries(8):
            response = self.client.post(
                reverse("invitation_list_create"), {"email": "invitee@example.com"}
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        invitation = Invitation.objects.get(email="invitee@example.com")
        self.assertEqual(invitation.organization, self.org_a)
        self.assertEqual(invitation.invited_by, self.admin_a)
        self.assertEqual(invitation.status, InvitationStatus.PENDING)
        self.assertTrue(invitation.token)
        mock_send_mail.assert_called_once()

    def test_invitations_are_listed_without_their_tokens(self):
        self.admin_a.name = "Ada Admin"
        self.admin_a.save(update_fields=["name"])
        InvitationFactory(
            organization=self.org_a, invited_by=self.admin_a, email="one@example.com"
        )
        InvitationFactory(
            organization=self.org_a, invited_by=self.admin_a, email="two@example.com"
        )
        self.client.force_authenticate(self.admin_a)

        with self.assertNumQueries(2):
            response = self.client.get(reverse("invitation_list_create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for row in response.data["results"]:
            self.assertNotIn("token", row)
            self.assertEqual(row["invited_by_email"], "admin-a@example.com")
            self.assertEqual(row["invited_by_name"], "Ada Admin")
            self.assertEqual(row["status"], InvitationStatus.PENDING)

    @patch("core.email.send_mail")
    def test_creating_an_invitation_does_not_return_its_token(self, mock_send_mail):
        self.client.force_authenticate(self.admin_a)

        with self.assertNumQueries(8):
            response = self.client.post(
                reverse("invitation_list_create"), {"email": "invitee@example.com"}
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("token", response.data)
        invitation = Invitation.objects.get(email="invitee@example.com")
        self.assertIn(invitation.token, mock_send_mail.call_args.kwargs["message"])

    def test_a_pending_invitation_past_its_expiry_is_listed_as_expired(self):
        invitation = InvitationFactory(organization=self.org_a, invited_by=self.admin_a)
        Invitation.objects.filter(pk=invitation.pk).update(
            sent_at=timezone.now() - settings.INVITATION_EXPIRY - timedelta(seconds=1)
        )
        self.client.force_authenticate(self.admin_a)

        with self.assertNumQueries(2):
            response = self.client.get(reverse("invitation_list_create"))

        self.assertEqual(
            response.data["results"][0]["status"], InvitationStatus.EXPIRED
        )

    @patch("core.email.send_mail")
    def test_an_expired_invitation_does_not_block_inviting_the_email_again(
        self, mock_send_mail
    ):
        expired = InvitationFactory(
            organization=self.org_a,
            invited_by=self.admin_a,
            email="again@example.com",
        )
        Invitation.objects.filter(pk=expired.pk).update(
            sent_at=timezone.now() - timedelta(days=999)
        )
        self.client.force_authenticate(self.admin_a)

        with self.assertNumQueries(8):
            response = self.client.post(
                reverse("invitation_list_create"), {"email": "again@example.com"}
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], InvitationStatus.PENDING)

    @patch("core.email.send_mail")
    def test_expired_invitations_do_not_count_toward_the_pending_cap(
        self, mock_send_mail
    ):
        expired = InvitationFactory(organization=self.org_a, invited_by=self.admin_a)
        Invitation.objects.filter(pk=expired.pk).update(
            sent_at=timezone.now() - timedelta(days=999)
        )
        self.client.force_authenticate(self.admin_a)

        with (
            patch("users.api.v1.serializers.MAX_PENDING_INVITATIONS_PER_ORG", 1),
            self.assertNumQueries(8),
        ):
            response = self.client.post(
                reverse("invitation_list_create"), {"email": "extra@example.com"}
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_non_admin_cannot_create_invitation(self):
        self.client.force_authenticate(self.member_a)

        with self.assertNumQueries(0):
            response = self.client.post(
                reverse("invitation_list_create"), {"email": "invitee@example.com"}
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            Invitation.objects.filter(email="invitee@example.com").exists()
        )

    def test_cannot_create_invitation_past_the_pending_cap(self):
        self.client.force_authenticate(self.admin_a)
        with patch("users.api.v1.serializers.MAX_PENDING_INVITATIONS_PER_ORG", 1):
            InvitationFactory(organization=self.org_a, invited_by=self.admin_a)

            with self.assertNumQueries(3):
                response = self.client.post(
                    reverse("invitation_list_create"), {"email": "extra@example.com"}
                )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_invite_an_email_that_already_belongs_to_a_user(self):
        self.client.force_authenticate(self.admin_a)

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("invitation_list_create"), {"email": self.member_a.email}
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Invitation.objects.filter(email=self.member_a.email).exists())

    @patch("core.email.send_mail")
    def test_can_invite_an_address_its_unverified_account_has_lost(
        self, mock_send_mail
    ):
        lapse_verification(
            AdminUserFactory(email="squatted@example.com", email_verified_at=None)
        )
        self.client.force_authenticate(self.admin_a)

        with self.assertNumQueries(8):
            response = self.client.post(
                reverse("invitation_list_create"), {"email": "squatted@example.com"}
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cannot_invite_an_email_with_an_existing_pending_invitation(self):
        InvitationFactory(
            organization=self.org_a,
            invited_by=self.admin_a,
            email="already-invited@example.com",
        )
        self.client.force_authenticate(self.admin_a)

        with self.assertNumQueries(2):
            response = self.client.post(
                reverse("invitation_list_create"),
                {"email": "already-invited@example.com"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Invitation.objects.filter(email="already-invited@example.com").count(), 1
        )

    def test_admin_cannot_see_invitations_outside_own_organization(self):
        InvitationFactory(
            organization=self.org_b,
            invited_by=self.admin_b,
            email="other-org-invitee@example.com",
            token="org-b-token",
        )

        self.client.force_authenticate(self.admin_a)
        with self.assertNumQueries(1):
            response = self.client.get(reverse("invitation_list_create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = [item["email"] for item in response.data["results"]]
        self.assertNotIn("other-org-invitee@example.com", emails)

    def test_accept_invitation_creates_user_and_logs_in(self):
        invitation = InvitationFactory(
            organization=self.org_a,
            invited_by=self.admin_a,
            email="new-user@example.com",
            token="valid-token",
        )

        with self.assertNumQueries(10):
            response = self.client.post(
                reverse("invitation_accept"),
                {"token": "valid-token", "password": "Str0ng-New-Pass!"},
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertEqual(
            response.cookies[settings.REFRESH_COOKIE_NAME].value,
            response.data["refresh"],
        )

        user = User.objects.get(email="new-user@example.com")
        self.assertEqual(user.organization, self.org_a)
        self.assertTrue(user.check_password("Str0ng-New-Pass!"))
        self.assertEqual(user.name, "")
        # The link was emailed to this address: following it proves it's theirs.
        self.assertTrue(user.email_verified)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatus.ACCEPTED)
        self.assertIsNotNone(invitation.accepted_at)

    def test_accept_invitation_records_the_name_given(self):
        InvitationFactory(
            organization=self.org_a, email="new-user@example.com", token="valid-token"
        )

        with self.assertNumQueries(10):
            response = self.client.post(
                reverse("invitation_accept"),
                {
                    "token": "valid-token",
                    "password": "Str0ng-New-Pass!",
                    "name": " Grace Hopper ",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="new-user@example.com")
        self.assertEqual(user.name, "Grace Hopper")

    def test_accept_invitation_twice_fails(self):
        InvitationFactory(
            organization=self.org_a,
            invited_by=self.admin_a,
            email="new-user@example.com",
            token="valid-token",
            status=InvitationStatus.ACCEPTED,
        )

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("invitation_accept"),
                {"token": "valid-token", "password": "Str0ng-New-Pass!"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_invitation_with_invalid_token_fails(self):
        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("invitation_accept"),
                {"token": "nonexistent-token", "password": "Str0ng-New-Pass!"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_invitation_rejects_a_password_missing_a_character_class(self):
        InvitationFactory(
            organization=self.org_a,
            invited_by=self.admin_a,
            email="new-user@example.com",
            token="valid-token",
        )

        with self.assertNumQueries(2):
            response = self.client.post(
                reverse("invitation_accept"),
                {"token": "valid-token", "password": "alllowercase1"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)
        self.assertNotIn("non_field_errors", response.data)
        self.assertFalse(User.objects.filter(email="new-user@example.com").exists())

    def test_accept_invitation_fails_once_expired(self):
        invitation = InvitationFactory(
            organization=self.org_a, invited_by=self.admin_a, token="valid-token"
        )
        stale = timezone.now() - timedelta(days=999)
        Invitation.objects.filter(pk=invitation.pk).update(sent_at=stale)

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("invitation_accept"),
                {"token": "valid-token", "password": "Str0ng-New-Pass!"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_invitation_fails_once_its_email_has_an_account(self):
        """e.g. the invitee signed up an organization of their own meanwhile:
        a refusal, not a clash creating a second user with the same email."""
        InvitationFactory(
            organization=self.org_a,
            invited_by=self.admin_a,
            email="taken@example.com",
            token="valid-token",
        )
        UserFactory(email="taken@example.com", organization=self.org_b)

        with self.assertNumQueries(2):
            response = self.client.post(
                reverse("invitation_accept"),
                {"token": "valid-token", "password": "Str0ng-New-Pass!"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["token"], ["This invitation link is invalid or has expired."]
        )
        self.assertEqual(User.objects.filter(email="taken@example.com").count(), 1)

    def test_accepting_takes_over_an_address_its_unverified_account_has_lost(self):
        squatter = AdminUserFactory(email="taken@example.com", email_verified_at=None)
        lapse_verification(squatter)
        InvitationFactory(
            organization=self.org_a, email="taken@example.com", token="valid-token"
        )

        response = self.client.post(
            reverse("invitation_accept"),
            {"token": "valid-token", "password": "Str0ng-New-Pass!"},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(
            Organization.objects.filter(pk=squatter.organization_id).exists()
        )
        self.assertEqual(
            User.objects.get(email="taken@example.com").organization, self.org_a
        )

    def test_accept_invitation_is_rate_limited(self):
        cache.clear()
        InvitationFactory(
            organization=self.org_a, invited_by=self.admin_a, token="tok-1"
        )
        with patch.object(
            ScopedRateThrottle, "THROTTLE_RATES", {"invite_accept": "1/min"}
        ):
            with self.assertNumQueries(1):
                self.client.post(
                    reverse("invitation_accept"),
                    {"token": "nope", "password": "Str0ng-New-Pass!"},
                )
            with self.assertNumQueries(0):
                throttled = self.client.post(
                    reverse("invitation_accept"),
                    {"token": "tok-1", "password": "Str0ng-New-Pass!"},
                )

        self.assertEqual(throttled.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_accept_invitation_is_rejected_at_the_locked_recheck(self):
        invitation = InvitationFactory(
            organization=self.org_a, invited_by=self.admin_a, token="tok"
        )
        Invitation.objects.filter(pk=invitation.pk).update(
            status=InvitationStatus.ACCEPTED
        )

        with (
            patch(
                "users.api.v1.views.InvitationAcceptSerializer.validate",
                side_effect=lambda attrs: {
                    "invitation": invitation,
                    "password": "Str0ng-New-Pass!",
                },
            ),
            self.assertNumQueries(3),
        ):
            response = self.client.post(
                reverse("invitation_accept"),
                {"token": "tok", "password": "Str0ng-New-Pass!"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CurrentUserAPITests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory(name="Acme")
        self.admin = AdminUserFactory(
            email="admin@example.com", name="Ada Admin", organization=self.org
        )
        self.member = UserFactory(email="member@example.com", organization=self.org)
        self.url = reverse("user_me")

    def test_admin_of_a_paid_organization_sees_role_and_active_subscription(self):
        StripeSubscriptionFactory(customer__subscriber=self.org)
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "id": self.admin.pk,
                "email": "admin@example.com",
                "email_verified": True,
                "name": "Ada Admin",
                "org_role": "ADMIN",
                "organization": {
                    "id": self.org.pk,
                    "name": "Acme",
                    "has_active_subscription": True,
                    "payment_failed": False,
                    "deletion_scheduled_for": None,
                },
            },
        )

    def test_says_when_a_renewal_payment_failed_and_access_continues(self):
        StripeSubscriptionFactory(customer__subscriber=self.org, status="past_due")
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["organization"]["has_active_subscription"])
        self.assertTrue(response.data["organization"]["payment_failed"])

    def test_member_of_an_unpaid_organization_is_not_blocked_with_402(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(1):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["org_role"], "MEMBER")
        self.assertFalse(response.data["organization"]["has_active_subscription"])

    def test_expired_subscription_is_reported_inactive(self):
        StripeSubscriptionFactory(customer__subscriber=self.org, status="canceled")
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertFalse(response.data["organization"]["has_active_subscription"])

    def test_an_unverified_signup_can_read_their_account(self):
        unverified = AdminUserFactory(organization=self.org, email_verified_at=None)
        self.client.force_authenticate(unverified)

        with self.assertNumQueries(1):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["email_verified"])

    def test_user_without_an_organization_gets_a_null_organization(self):
        rootless_admin = AdminUserFactory(organization=None)
        self.client.force_authenticate(rootless_admin)

        with self.assertNumQueries(0):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["organization"])

    def test_schema_documents_the_organization_as_nullable(self):
        with self.assertNumQueries(0):
            response = self.client.get(reverse("schema"), {"format": "json"})

        organization = response.data["components"]["schemas"]["CurrentUser"][
            "properties"
        ]["organization"]
        self.assertTrue(organization["nullable"])

    def test_schema_always_includes_the_name_in_the_response(self):
        with self.assertNumQueries(0):
            response = self.client.get(reverse("schema"), {"format": "json"})

        current_user = response.data["components"]["schemas"]["CurrentUser"]
        self.assertIn("name", current_user["required"])

    def test_changes_own_name_without_needing_a_subscription(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.patch(self.url, {"name": "  Grace Hopper "})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Grace Hopper")
        self.member.refresh_from_db()
        self.assertEqual(self.member.name, "Grace Hopper")

    def test_clears_own_name(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(2):
            response = self.client.patch(self.url, {"name": ""})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.name, "")

    def test_only_the_name_can_be_changed(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.patch(
                self.url,
                {"name": "Grace", "email": "taken@example.com", "org_role": "ADMIN"},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.member.refresh_from_db()
        self.assertEqual(self.member.name, "Grace")
        self.assertEqual(self.member.email, "member@example.com")
        self.assertEqual(self.member.org_role, "MEMBER")

    def test_refuses_a_name_over_the_length_limit(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(0):
            response = self.client.patch(
                self.url, {"name": "x" * (MAX_NAME_LENGTH + 1)}
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_an_unverified_signup_cannot_change_their_name(self):
        unverified = AdminUserFactory(organization=self.org, email_verified_at=None)
        self.client.force_authenticate(unverified)

        with self.assertNumQueries(0):
            response = self.client.patch(self.url, {"name": "Grace"})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "email_unverified")

    def test_a_full_replace_is_not_offered(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(0):
            response = self.client.put(self.url, {"name": "Grace"})

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_anonymous_request_is_rejected(self):
        with self.assertNumQueries(0):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_anonymous_name_change_is_rejected(self):
        with self.assertNumQueries(0):
            response = self.client.patch(self.url, {"name": "Grace"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class InvitationRevokeResendTests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.org = OrganizationFactory(name="Acme")
        self.admin = AdminUserFactory(organization=self.org)
        self.member = UserFactory(organization=self.org)
        self.invitation = InvitationFactory(
            organization=self.org, invited_by=self.admin, token="first-token"
        )
        self.revoke_url = reverse("invitation_revoke", args=[self.invitation.pk])
        self.resend_url = reverse("invitation_resend", args=[self.invitation.pk])

    @patch("core.email.send_mail")
    def test_resend_rotates_the_token_and_restarts_the_expiry_window(
        self, mock_send_mail
    ):
        stale = timezone.now() - timedelta(days=999)
        Invitation.objects.filter(pk=self.invitation.pk).update(sent_at=stale)
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(8):
            response = self.client.post(self.resend_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.invitation.refresh_from_db()
        self.assertNotEqual(self.invitation.token, "first-token")
        self.assertNotIn("token", response.data)
        self.assertEqual(response.data["status"], InvitationStatus.PENDING)
        self.assertGreater(self.invitation.sent_at, stale)
        mock_send_mail.assert_called_once()
        self.assertIn(self.invitation.token, mock_send_mail.call_args.kwargs["message"])

        self.client.force_authenticate(None)
        old_link = self.client.post(
            reverse("invitation_accept"),
            {"token": "first-token", "password": "Str0ng-New-Pass!"},
        )
        self.assertEqual(old_link.status_code, status.HTTP_400_BAD_REQUEST)
        new_link = self.client.post(
            reverse("invitation_accept"),
            {"token": self.invitation.token, "password": "Str0ng-New-Pass!"},
        )
        self.assertEqual(new_link.status_code, status.HTTP_201_CREATED)

    def test_resend_rejects_an_invitation_that_is_no_longer_pending(self):
        Invitation.objects.filter(pk=self.invitation.pk).update(
            status=InvitationStatus.ACCEPTED
        )
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(1):
            response = self.client.post(self.resend_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_refuses_an_expired_invitation_replaced_by_a_newer_one(self):
        Invitation.objects.filter(pk=self.invitation.pk).update(
            sent_at=timezone.now() - timedelta(days=999)
        )
        InvitationFactory(
            organization=self.org, invited_by=self.admin, email=self.invitation.email
        )
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(3):
            response = self.client.post(self.resend_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"], "This email already has a pending invitation."
        )
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.token, "first-token")

    def test_resend_refuses_once_the_email_has_an_account(self):
        UserFactory(email=self.invitation.email)
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(2):
            response = self.client.post(self.resend_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"], "A user with this email already exists."
        )

    def test_revoke_marks_the_invitation_revoked_and_kills_its_link(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(5):
            response = self.client.delete(self.revoke_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, InvitationStatus.REVOKED)

        self.client.force_authenticate(None)
        accept = self.client.post(
            reverse("invitation_accept"),
            {"token": "first-token", "password": "Str0ng-New-Pass!"},
        )
        self.assertEqual(accept.status_code, status.HTTP_400_BAD_REQUEST)

    def test_revoke_rejects_an_invitation_that_is_no_longer_pending(self):
        Invitation.objects.filter(pk=self.invitation.pk).update(
            status=InvitationStatus.REVOKED
        )
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(1):
            response = self.client.delete(self.revoke_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_another_organizations_invitation_is_a_404(self):
        self.client.force_authenticate(AdminUserFactory())

        with self.assertNumQueries(1):
            revoke = self.client.delete(self.revoke_url)
        with self.assertNumQueries(1):
            resend = self.client.post(self.resend_url)

        self.assertEqual(revoke.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resend.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_cannot_revoke_or_resend(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(0):
            revoke = self.client.delete(self.revoke_url)
        with self.assertNumQueries(0):
            resend = self.client.post(self.resend_url)

        self.assertEqual(revoke.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resend.status_code, status.HTTP_403_FORBIDDEN)


class UserListAPITests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.org = OrganizationFactory(name="Org A")
        self.other_org = OrganizationFactory(name="Org B")
        self.admin = AdminUserFactory(
            email="admin@example.com", name="Grace Hopper", organization=self.org
        )
        self.member = UserFactory(email="member@example.com", organization=self.org)
        self.url = reverse("user_list")

    def test_member_can_list_own_organization_users_ordered_by_email(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = [row["email"] for row in response.data["results"]]
        self.assertEqual(emails, ["admin@example.com", "member@example.com"])

    def test_member_only_sees_id_email_and_name(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(
            [(row["email"], row["name"]) for row in response.data["results"]],
            [("admin@example.com", "Grace Hopper"), ("member@example.com", "")],
        )
        for row in response.data["results"]:
            self.assertEqual(set(row.keys()), {"id", "email", "name"})

    def test_admin_also_sees_role_and_join_date(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        for row in response.data["results"]:
            self.assertEqual(
                set(row.keys()), {"id", "email", "name", "org_role", "created"}
            )

    def test_schema_documents_both_the_admin_and_member_shapes(self):
        with self.assertNumQueries(0):
            response = self.client.get(reverse("schema"), {"format": "json"})

        schemas = response.data["components"]["schemas"]
        rows = schemas["PaginatedRosterUserList"]["properties"]["results"]["items"]
        self.assertEqual(rows["$ref"], "#/components/schemas/RosterUser")
        self.assertEqual(
            schemas["RosterUser"]["oneOf"],
            [
                {"$ref": "#/components/schemas/UserDetail"},
                {"$ref": "#/components/schemas/User"},
            ],
        )

    def test_excludes_users_from_other_organizations(self):
        UserFactory(email="outsider@example.com", organization=self.other_org)
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        emails = [row["email"] for row in response.data["results"]]
        self.assertNotIn("outsider@example.com", emails)

    def test_excludes_deactivated_users(self):
        UserFactory(email="gone@example.com", organization=self.org, is_active=False)
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        emails = [row["email"] for row in response.data["results"]]
        self.assertNotIn("gone@example.com", emails)

    def test_search_filters_by_email(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url, {"search": "admin"})

        emails = [row["email"] for row in response.data["results"]]
        self.assertEqual(emails, ["admin@example.com"])

    def test_search_also_matches_names(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url, {"search": "hopper"})

        emails = [row["email"] for row in response.data["results"]]
        self.assertEqual(emails, ["admin@example.com"])

    def test_user_without_an_organization_sees_an_empty_list(self):
        rootless_admin = AdminUserFactory(organization=None)
        self.client.force_authenticate(rootless_admin)

        with self.assertNumQueries(0):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_anonymous_request_is_rejected(self):
        with self.assertNumQueries(0):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DeactivateUserTests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.org = OrganizationFactory(name="Org A")
        self.other_org = OrganizationFactory(name="Org B")

        self.admin = AdminUserFactory(email="admin@example.com", organization=self.org)
        self.member = UserFactory(
            email="member@example.com",
            organization=self.org,
            password="Member-Pass-123!",
        )
        self.other_org_user = UserFactory(
            email="outsider@example.com", organization=self.other_org
        )

    def _url(self, user):
        return reverse("user_deactivate", kwargs={"pk": user.pk})

    def test_admin_deactivates_a_user_in_their_own_organization(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(7):
            response = self.client.delete(self._url(self.member))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)

    def test_an_admin_demoted_meanwhile_can_no_longer_deactivate_anyone(self):
        User.objects.filter(pk=self.admin.pk).update(org_role=OrganizationRole.MEMBER)
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(6):
            response = self.client.delete(self._url(self.member))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)

    def test_admin_cannot_deactivate_a_user_in_another_organization(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(1):
            response = self.client.delete(self._url(self.other_org_user))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.other_org_user.refresh_from_db()
        self.assertTrue(self.other_org_user.is_active)

    def test_admin_cannot_deactivate_themselves(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(1):
            response = self.client.delete(self._url(self.admin))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_non_admin_cannot_deactivate_a_user(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(0):
            response = self.client.delete(self._url(self.other_org_user))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_request_is_rejected(self):
        with self.assertNumQueries(0):
            response = self.client.delete(self._url(self.member))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_deactivated_user_can_no_longer_log_in(self):
        self.client.force_authenticate(self.admin)
        self.client.delete(self._url(self.member))
        self.client.force_authenticate(user=None)

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("auth_login"),
                {"email": self.member.email, "password": "Member-Pass-123!"},
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class OrganizationRoleUpdateTests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.org = OrganizationFactory()
        self.admin = AdminUserFactory(organization=self.org)
        self.member = UserFactory(organization=self.org)

    def _url(self, user):
        return reverse("user_role_update", args=[user.pk])

    def test_an_admin_demoted_meanwhile_can_no_longer_change_roles(self):
        # The request was authenticated as an admin, but by the time it holds
        # the organization's lock, another admin has made them a member.
        User.objects.filter(pk=self.admin.pk).update(org_role=OrganizationRole.MEMBER)
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(6):
            response = self.client.patch(
                self._url(self.member), {"org_role": OrganizationRole.ADMIN}
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["detail"], NO_LONGER_ADMIN_MESSAGE)
        self.member.refresh_from_db()
        self.assertEqual(self.member.org_role, OrganizationRole.MEMBER)

    def test_admin_promotes_a_member_to_admin(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(7):
            response = self.client.patch(
                self._url(self.member), {"org_role": "ADMIN"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["org_role"], "ADMIN")
        self.member.refresh_from_db()
        self.assertEqual(self.member.org_role, "ADMIN")

    def test_admin_demotes_another_admin(self):
        other_admin = AdminUserFactory(organization=self.org)
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(7):
            response = self.client.patch(
                self._url(other_admin), {"org_role": "MEMBER"}, format="json"
            )

        self.assertEqual(response.data["org_role"], "MEMBER")

    def test_admin_cannot_change_their_own_role(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(0):
            response = self.client.patch(
                self._url(self.admin), {"org_role": "MEMBER"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_an_unknown_role(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(1):
            response = self.client.patch(
                self._url(self.member), {"org_role": "OWNER"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deactivated_and_other_organization_users_are_a_404(self):
        deactivated = UserFactory(organization=self.org, is_active=False)
        outsider = UserFactory()
        self.client.force_authenticate(self.admin)

        for target in (deactivated, outsider):
            with self.assertNumQueries(1):
                response = self.client.patch(
                    self._url(target), {"org_role": "ADMIN"}, format="json"
                )
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_cannot_change_roles(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(0):
            response = self.client.patch(
                self._url(self.admin), {"org_role": "MEMBER"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DeactivatedUserListAndReactivateTests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.org = OrganizationFactory()
        self.admin = AdminUserFactory(organization=self.org)
        self.member = UserFactory(organization=self.org)
        self.deactivated = UserFactory(
            email="gone@example.com", organization=self.org, is_active=False
        )
        UserFactory(email="elsewhere@example.com", is_active=False)

    def test_admin_lists_only_their_organizations_deactivated_users(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(2):
            response = self.client.get(reverse("user_deactivated_list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = [row["email"] for row in response.data["results"]]
        self.assertEqual(emails, ["gone@example.com"])

    def test_admin_reactivates_a_deactivated_user(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(5):
            response = self.client.post(
                reverse("user_reactivate", args=[self.deactivated.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.deactivated.refresh_from_db()
        self.assertTrue(self.deactivated.is_active)

    def test_reactivating_an_active_or_outside_user_is_a_404(self):
        outsider = User.objects.get(email="elsewhere@example.com")
        self.client.force_authenticate(self.admin)

        for target in (self.member, outsider):
            with self.assertNumQueries(1):
                response = self.client.post(
                    reverse("user_reactivate", args=[target.pk])
                )
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_can_neither_list_nor_reactivate(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(0):
            listing = self.client.get(reverse("user_deactivated_list"))
        with self.assertNumQueries(0):
            reactivate = self.client.post(
                reverse("user_reactivate", args=[self.deactivated.pk])
            )

        self.assertEqual(listing.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(reactivate.status_code, status.HTTP_403_FORBIDDEN)


class UserManagerTests(TestCase):
    def test_create_user_requires_an_email(self):
        with self.assertNumQueries(0), self.assertRaises(ValueError):
            User.objects.create_user(email="", password="whatever")

    def test_create_superuser_sets_staff_and_superuser(self):
        with self.assertNumQueries(1):
            admin = User.objects.create_superuser(
                email="root@example.com", password="R00t-Pass!"
            )

        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        # Created from the command line, not by signing up: nothing to verify.
        self.assertTrue(admin.email_verified)

    def test_create_superuser_rejects_non_staff(self):
        with self.assertNumQueries(0), self.assertRaises(ValueError):
            User.objects.create_superuser(
                email="root@example.com", password="R00t-Pass!", is_staff=False
            )

    def test_create_superuser_rejects_non_superuser(self):
        with self.assertNumQueries(0), self.assertRaises(ValueError):
            User.objects.create_superuser(
                email="root@example.com", password="R00t-Pass!", is_superuser=False
            )


class UnverifiedAccountRemovalTests(TestCase):
    def setUp(self):
        self.lapsed = AdminUserFactory(email_verified_at=None)
        lapse_verification(self.lapsed)

    def test_removes_signups_that_never_verified_with_their_organizations(self):
        waiting = AdminUserFactory(email_verified_at=None)
        verified = AdminUserFactory()

        remove_unverified_accounts_task.delay()

        self.assertFalse(User.objects.filter(pk=self.lapsed.pk).exists())
        self.assertFalse(
            Organization.objects.filter(pk=self.lapsed.organization_id).exists()
        )
        self.assertTrue(User.objects.filter(pk=waiting.pk).exists())
        self.assertTrue(User.objects.filter(pk=verified.pk).exists())

    def test_leaves_an_organization_with_a_verified_member_alone(self):
        UserFactory(organization=self.lapsed.organization)

        remove_unverified_accounts_task.delay()

        self.assertTrue(User.objects.filter(pk=self.lapsed.pk).exists())

    def test_an_account_that_never_verified_in_time_no_longer_holds_its_address(self):
        holders = User.objects.holding_email()

        self.assertFalse(holders.filter(pk=self.lapsed.pk).exists())


class PasswordComplexityTests(SimpleTestCase):
    def setUp(self):
        self.validator = ComplexityValidator()

    def test_accepts_a_password_with_every_character_class(self):
        self.validator.validate("Abcdef1!")  # no raise

    def test_rejects_a_password_missing_any_class(self):
        for weak in ("ABCDEF1!", "abcdef1!", "Abcdefg!", "Abcdefg1"):
            with self.assertRaises(ValidationError):
                self.validator.validate(weak)

    def test_help_text_lists_the_requirements(self):
        self.assertIn("special character", self.validator.get_help_text())


class MaximumLengthValidatorTests(SimpleTestCase):
    def setUp(self):
        self.validator = MaximumLengthValidator(max_length=10)

    def test_accepts_within_limit(self):
        self.validator.validate("short")  # no raise

    def test_rejects_over_limit(self):
        with self.assertRaises(ValidationError):
            self.validator.validate("x" * 11)

    def test_help_text_mentions_the_limit(self):
        self.assertIn("10", self.validator.get_help_text())


class ModelStrTests(TestCase):
    def test_user_str_is_the_email(self):
        user = UserFactory(email="person@example.com", organization=None)

        with self.assertNumQueries(0):
            self.assertEqual(str(user), "person@example.com")

    def test_user_full_name_is_their_name(self):
        user = UserFactory(name="Grace Hopper", organization=None)

        with self.assertNumQueries(0):
            self.assertEqual(user.get_full_name(), "Grace Hopper")
            self.assertEqual(user.get_short_name(), "Grace Hopper")

    def test_user_is_named_by_name_and_email_or_the_email_alone(self):
        named = UserFactory(
            email="grace@example.com", name="Grace Hopper", organization=None
        )
        unnamed = UserFactory(email="person@example.com", organization=None)

        with self.assertNumQueries(0):
            self.assertEqual(named.name_and_email, "Grace Hopper (grace@example.com)")
            self.assertEqual(unnamed.name_and_email, "person@example.com")

    def test_invitation_str_includes_email_and_status(self):
        invitation = InvitationFactory(email="invitee@example.com")

        with self.assertNumQueries(0):
            self.assertEqual(str(invitation), "invitee@example.com (PENDING)")


class InvitationStatusTests(TestCase):
    """Expiry is worked out on read: a stored PENDING row past
    INVITATION_EXPIRY reads as EXPIRED, and drops out of ``pending()``."""

    def setUp(self):
        self.fresh = InvitationFactory()
        self.stale = InvitationFactory(organization=self.fresh.organization)
        Invitation.objects.filter(pk=self.stale.pk).update(
            sent_at=timezone.now() - settings.INVITATION_EXPIRY - timedelta(seconds=1)
        )
        self.stale.refresh_from_db()

    def test_a_fresh_pending_invitation_is_pending(self):
        self.assertFalse(self.fresh.is_expired)
        self.assertEqual(self.fresh.current_status, InvitationStatus.PENDING)

    def test_a_pending_invitation_past_its_expiry_reads_as_expired(self):
        self.assertTrue(self.stale.is_expired)
        self.assertEqual(self.stale.current_status, InvitationStatus.EXPIRED)
        self.assertEqual(self.stale.status, InvitationStatus.PENDING)

    def test_a_settled_invitation_keeps_its_status_however_old(self):
        Invitation.objects.filter(pk=self.stale.pk).update(
            status=InvitationStatus.ACCEPTED
        )
        self.stale.refresh_from_db()

        self.assertFalse(self.stale.is_expired)
        self.assertEqual(self.stale.current_status, InvitationStatus.ACCEPTED)

    def test_pending_leaves_out_expired_and_settled_invitations(self):
        InvitationFactory(
            organization=self.fresh.organization, status=InvitationStatus.REVOKED
        )

        with self.assertNumQueries(1):
            pending = list(Invitation.objects.pending())

        self.assertEqual(pending, [self.fresh])


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class InvitationBulkCreateTests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.org_a = OrganizationFactory(name="Org A")
        self.admin_a = AdminUserFactory(
            email="admin-a@example.com", organization=self.org_a
        )
        self.member_a = UserFactory(
            email="member-a@example.com", organization=self.org_a
        )

    @patch("core.email.send_mail")
    def test_valid_file_creates_invitations_and_sends_emails(self, mock_send_mail):
        self.client.force_authenticate(self.admin_a)
        upload = build_xlsx_upload(["Email", "one@example.com", "two@example.com"])

        with self.assertNumQueries(13):
            response = self.client.post(
                reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created"], 2)
        self.assertEqual(response.data["skipped"], [])
        self.assertEqual(mock_send_mail.call_count, 2)
        self.assertTrue(Invitation.objects.filter(email="one@example.com").exists())
        self.assertTrue(Invitation.objects.filter(email="two@example.com").exists())

    @patch("core.email.send_mail")
    def test_file_without_a_header_row_still_parses(self, mock_send_mail):
        self.client.force_authenticate(self.admin_a)
        upload = build_xlsx_upload(["one@example.com", "two@example.com"])

        with self.assertNumQueries(13):
            response = self.client.post(
                reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created"], 2)
        self.assertEqual(response.data["skipped"], [])

    @patch("core.email.send_mail")
    def test_duplicate_email_in_file_is_skipped(self, mock_send_mail):
        self.client.force_authenticate(self.admin_a)
        upload = build_xlsx_upload(["Email", "dupe@example.com", "DUPE@example.com"])

        with self.assertNumQueries(8):
            response = self.client.post(
                reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created"], 1)
        self.assertEqual(response.data["skipped"][0]["email"], "DUPE@example.com")
        self.assertEqual(response.data["skipped"][0]["reason"], "duplicate in file")
        mock_send_mail.assert_called_once()

    @patch("core.email.send_mail")
    def test_overlong_email_is_skipped(self, mock_send_mail):
        self.client.force_authenticate(self.admin_a)
        overlong_email = ("a" * 250) + "@example.com"
        upload = build_xlsx_upload(["Email", overlong_email])

        with self.assertNumQueries(3):
            response = self.client.post(
                reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created"], 0)
        self.assertEqual(response.data["skipped"][0]["reason"], "email too long")
        mock_send_mail.assert_not_called()

    @patch("core.email.send_mail")
    def test_malformed_rows_are_skipped_without_failing_batch(self, mock_send_mail):
        self.client.force_authenticate(self.admin_a)
        upload = build_xlsx_upload(["Email", "not-an-email", "valid@example.com"])

        with self.assertNumQueries(8):
            response = self.client.post(
                reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created"], 1)
        self.assertEqual(len(response.data["skipped"]), 1)
        self.assertEqual(response.data["skipped"][0]["email"], "not-an-email")
        self.assertEqual(response.data["skipped"][0]["reason"], "invalid email")
        mock_send_mail.assert_called_once()

    @patch("core.email.send_mail")
    def test_existing_user_and_pending_invitation_are_skipped(self, mock_send_mail):
        UserFactory(email="existing@example.com", organization=self.org_a)
        InvitationFactory(
            organization=self.org_a,
            invited_by=self.admin_a,
            email="pending@example.com",
            token="already-pending-token",
        )
        self.client.force_authenticate(self.admin_a)
        upload = build_xlsx_upload(
            ["Email", "existing@example.com", "pending@example.com", "new@example.com"]
        )

        with self.assertNumQueries(8):
            response = self.client.post(
                reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created"], 1)
        reasons = {item["email"]: item["reason"] for item in response.data["skipped"]}
        self.assertEqual(reasons["existing@example.com"], "user already exists")
        self.assertEqual(reasons["pending@example.com"], "invitation already pending")
        mock_send_mail.assert_called_once()
        self.assertTrue(Invitation.objects.filter(email="new@example.com").exists())

    @patch("core.email.send_mail")
    def test_an_expired_invitation_does_not_block_its_row(self, mock_send_mail):
        expired = InvitationFactory(
            organization=self.org_a, invited_by=self.admin_a, email="late@example.com"
        )
        Invitation.objects.filter(pk=expired.pk).update(
            sent_at=timezone.now() - timedelta(days=999)
        )
        self.client.force_authenticate(self.admin_a)
        upload = build_xlsx_upload(["late@example.com"])

        with self.assertNumQueries(8):
            response = self.client.post(
                reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data, {"created": 1, "skipped": []})

    @patch("core.email.send_mail")
    def test_a_user_from_another_organization_is_skipped_not_invited(
        self, mock_send_mail
    ):
        other_org = OrganizationFactory(name="Org B")
        UserFactory(email="outsider@example.com", organization=other_org)
        self.client.force_authenticate(self.admin_a)
        upload = build_xlsx_upload(["Email", "outsider@example.com"])

        with self.assertNumQueries(3):
            response = self.client.post(
                reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created"], 0)
        self.assertEqual(response.data["skipped"][0]["reason"], "user already exists")
        mock_send_mail.assert_not_called()
        self.assertFalse(
            Invitation.objects.filter(
                organization=self.org_a, email="outsider@example.com"
            ).exists()
        )

    def test_cannot_create_invitations_past_the_pending_cap(self):
        self.client.force_authenticate(self.admin_a)
        upload = build_xlsx_upload(["Email", "one@example.com", "two@example.com"])

        with (
            patch("users.services.MAX_PENDING_INVITATIONS_PER_ORG", 1),
            self.assertNumQueries(8),
        ):
            response = self.client.post(
                reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created"], 1)
        reasons = {item["email"]: item["reason"] for item in response.data["skipped"]}
        self.assertEqual(
            reasons["two@example.com"],
            "organization has too many pending invitations",
        )

    def test_non_admin_cannot_bulk_create_invitations(self):
        self.client.force_authenticate(self.member_a)
        upload = build_xlsx_upload(["Email", "someone@example.com"])

        with self.assertNumQueries(0):
            response = self.client.post(
                reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            Invitation.objects.filter(email="someone@example.com").exists()
        )

    def test_missing_file_is_rejected(self):
        self.client.force_authenticate(self.admin_a)

        with self.assertNumQueries(0):
            response = self.client.post(
                reverse("invitation_bulk_create"), {}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "file is required.")

    def test_invalid_file_is_rejected(self):
        self.client.force_authenticate(self.admin_a)
        not_xlsx = SimpleUploadedFile(
            "bad.xlsx", b"not an xlsx file", content_type=XLSX_CONTENT_TYPE
        )

        with self.assertNumQueries(0):
            response = self.client.post(
                reverse("invitation_bulk_create"),
                {"file": not_xlsx},
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"], "file must be a valid .xlsx workbook."
        )

    def test_file_over_row_limit_is_rejected(self):
        self.client.force_authenticate(self.admin_a)
        rows = ["Email"] + [
            f"user{i}@example.com" for i in range(MAX_BULK_INVITE_ROWS + 1)
        ]
        upload = build_xlsx_upload(rows)

        with self.assertNumQueries(0):
            response = self.client.post(
                reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Invitation.objects.exists())


# How long a request waits for the other one at the point where, without the
# lock, both would have passed their check. With the lock the other request is
# still waiting for it, so this times out and the first carries on alone.
RACE_WAIT_SECONDS = 2


@skipUnlessDBFeature("has_select_for_update")
class ConcurrentAdminChangeTests(AssumeActiveSubscription, TransactionTestCase):
    """Real concurrent requests, so only on a database with row locks
    (Postgres: CI and `make test-pg`)."""

    def test_two_admins_demoting_each_other_at_once_leave_one_admin(self):
        organization = OrganizationFactory()
        first, second = AdminUserFactory.create_batch(2, organization=organization)
        both_checked = threading.Barrier(2)
        save_role = user_views.OrganizationRoleSerializer.save
        responses = []

        def save_after_the_other_checked(serializer, **kwargs):
            with contextlib.suppress(threading.BrokenBarrierError):
                both_checked.wait(timeout=RACE_WAIT_SECONDS)
            return save_role(serializer, **kwargs)

        def demote(admin, other_admin):
            client = APIClient()
            client.force_authenticate(admin)
            try:
                responses.append(
                    client.patch(
                        reverse("user_role_update", args=[other_admin.pk]),
                        {"org_role": OrganizationRole.MEMBER},
                    )
                )
            finally:
                connection.close()

        with patch.object(
            user_views.OrganizationRoleSerializer,
            "save",
            autospec=True,
            side_effect=save_after_the_other_checked,
        ):
            requests = [
                threading.Thread(target=demote, args=(first, second)),
                threading.Thread(target=demote, args=(second, first)),
            ]
            for request in requests:
                request.start()
            for request in requests:
                request.join()

        self.assertEqual(
            sorted(response.status_code for response in responses),
            [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN],
        )
        self.assertEqual(
            User.objects.filter(
                organization=organization, org_role=OrganizationRole.ADMIN
            ).count(),
            1,
        )


class AccountDeletionTests(AssumeActiveSubscription, APITestCase):
    url = reverse("user_account_delete")

    def setUp(self):
        super().setUp()
        self.org = OrganizationFactory()
        self.admin = AdminUserFactory(organization=self.org)
        self.member = UserFactory(
            organization=self.org, name="Mia", email="mia@example.com"
        )
        self.document = DocumentFactory(
            project=None, organization=self.org, created_by=self.admin
        )
        DocumentPermissionFactory(
            document=self.document, user=self.admin, access_level=AccessLevel.OWNER
        )
        self.client.force_authenticate(self.member)

    def delete_account(self, password=DEFAULT_TEST_PASSWORD, queries=0):
        with self.assertNumQueries(queries):
            return self.client.post(self.url, {"current_password": password})

    def test_a_member_deletes_their_account_which_is_anonymised(self):
        written = DocumentFactory(
            project=None, organization=self.org, created_by=self.member
        )
        for user in (self.admin, self.member):
            DocumentPermissionFactory(
                document=written, user=user, access_level=AccessLevel.OWNER
            )
        DocumentPermissionFactory(
            document=self.document, user=self.member, access_level=AccessLevel.EDITOR
        )
        pending = DocumentAccessRequestFactory(
            document=self.document, requested_by=self.member
        )
        answered = DocumentAccessRequestFactory(
            document=written,
            requested_by=self.member,
            status=AccessRequestStatus.DENIED,
        )
        NotificationFactory(recipient=self.member)
        RefreshToken.for_user(self.member)

        response = self.delete_account(queries=16)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.cookies[settings.REFRESH_COOKIE_NAME].value, "")
        self.member.refresh_from_db()
        self.assertEqual(
            (
                self.member.email,
                self.member.name,
                self.member.is_active,
                self.member.has_usable_password(),
                bool(self.member.deleted_at),
            ),
            (
                f"deleted-{self.member.pk}@deleted.invalid",
                "Deleted user",
                False,
                False,
                True,
            ),
        )
        # What they wrote keeps its (now anonymous) author; their access,
        # pending request and notifications are gone, answered requests kept.
        written.refresh_from_db()
        self.assertEqual(written.created_by, self.member)
        self.assertFalse(DocumentPermission.objects.filter(user=self.member).exists())
        self.assertFalse(DocumentAccessRequest.objects.filter(pk=pending.pk).exists())
        self.assertTrue(DocumentAccessRequest.objects.filter(pk=answered.pk).exists())
        self.assertFalse(self.member.notifications.exists())
        self.assertFalse(
            OutstandingToken.objects.filter(user=self.member)
            .exclude(blacklistedtoken__isnull=False)
            .exists()
        )
        self.assertEqual(
            list(AuditEvent.objects.values_list("actor", "verb")),
            [(self.member.pk, AuditVerb.ACCOUNT_DELETED)],
        )

    def test_the_old_address_can_no_longer_sign_in_and_is_free_again(self):
        self.delete_account(queries=12)
        self.client.force_authenticate(None)

        with self.assertNumQueries(1):
            login = self.client.post(
                reverse("auth_login"),
                {"email": "mia@example.com", "password": DEFAULT_TEST_PASSWORD},
            )
        self.client.force_authenticate(self.admin)
        with self.assertNumQueries(8):
            invite = self.client.post(
                reverse("invitation_list_create"), {"email": "mia@example.com"}
            )

        self.assertEqual(login.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(invite.status_code, status.HTTP_201_CREATED)

    def test_a_deleted_account_is_neither_deactivated_nor_reactivatable(self):
        self.delete_account(queries=12)
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(1):
            listed = self.client.get(reverse("user_deactivated_list"))
        with self.assertNumQueries(1):
            reactivated = self.client.post(
                reverse("user_reactivate", args=[self.member.pk])
            )

        self.assertEqual(listed.data["count"], 0)
        self.assertEqual(reactivated.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_wrong_password_changes_nothing(self):
        response = self.delete_account(password="Wrong-Pass-123!", queries=0)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_password", response.data)
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)

    def test_the_only_owner_of_something_is_refused(self):
        sole = DocumentFactory(
            project=None, organization=self.org, created_by=self.member
        )
        DocumentPermissionFactory(
            document=sole, user=self.member, access_level=AccessLevel.OWNER
        )

        response = self.delete_account(queries=6)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            str(response.data["detail"]), sole_owner_message(projects=0, documents=1)
        )
        self.member.refresh_from_db()
        self.assertEqual(
            (self.member.is_active, self.member.email), (True, "mia@example.com")
        )

    def test_the_organizations_only_admin_is_refused(self):
        self.client.force_authenticate(self.admin)

        response = self.delete_account(queries=5)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data["detail"]), LAST_ADMIN_LEAVING_MESSAGE)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_an_admin_may_leave_while_another_admin_remains(self):
        leaving = AdminUserFactory(organization=self.org)
        self.client.force_authenticate(leaving)

        response = self.delete_account(queries=13)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_signing_in_is_required(self):
        self.client.force_authenticate(None)

        response = self.delete_account(queries=0)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@skipUnlessDBFeature("has_select_for_update")
class ConcurrentAccountDeletionTests(AssumeActiveSubscription, TransactionTestCase):
    """Real concurrent requests, so only on a database with row locks
    (Postgres: CI and `make test-pg`)."""

    def test_two_admins_leaving_at_once_leave_one_admin(self):
        organization = OrganizationFactory()
        admins = AdminUserFactory.create_batch(2, organization=organization)
        both_checked = threading.Barrier(2)
        revoke_sessions = user_services.blacklist_outstanding_tokens
        responses = []

        def revoke_after_the_other_checked(user):
            with contextlib.suppress(threading.BrokenBarrierError):
                both_checked.wait(timeout=RACE_WAIT_SECONDS)
            return revoke_sessions(user)

        def leave(admin):
            client = APIClient()
            client.force_authenticate(admin)
            try:
                responses.append(
                    client.post(
                        reverse("user_account_delete"),
                        {"current_password": DEFAULT_TEST_PASSWORD},
                    )
                )
            finally:
                connection.close()

        with patch.object(
            user_services,
            "blacklist_outstanding_tokens",
            side_effect=revoke_after_the_other_checked,
        ):
            requests = [
                threading.Thread(target=leave, args=(admin,)) for admin in admins
            ]
            for request in requests:
                request.start()
            for request in requests:
                request.join()

        self.assertEqual(
            sorted(response.status_code for response in responses),
            [status.HTTP_204_NO_CONTENT, status.HTTP_400_BAD_REQUEST],
        )
        self.assertEqual(
            User.objects.filter(
                organization=organization,
                org_role=OrganizationRole.ADMIN,
                is_active=True,
            ).count(),
            1,
        )
