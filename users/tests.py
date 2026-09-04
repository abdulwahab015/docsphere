from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from openpyxl import Workbook
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from organizations.factories import OrganizationFactory
from users.choices import InvitationStatus
from users.constants import MAX_BULK_INVITE_ROWS
from users.factories import AdminUserFactory, InvitationFactory, UserFactory
from users.models import Invitation
from users.password_validation import ComplexityValidator, MaximumLengthValidator

User = get_user_model()

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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
        with self.assertNumQueries(2):
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

        with self.assertNumQueries(2):
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
        with self.assertNumQueries(2):
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
        with self.assertNumQueries(2):
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
        with self.assertNumQueries(2):
            login = self.client.post(
                reverse("auth_login"),
                {"email": self.user.email, "password": "Old-Pass-123!"},
            )
        old_refresh = login.data["refresh"]

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


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class InvitationTests(APITestCase):
    def setUp(self):
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

        with self.assertNumQueries(3):
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

            with self.assertNumQueries(1):
                response = self.client.post(
                    reverse("invitation_list_create"), {"email": "extra@example.com"}
                )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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

        with self.assertNumQueries(7):
            response = self.client.post(
                reverse("invitation_accept"),
                {"token": "valid-token", "password": "Str0ng-New-Pass!"},
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        user = User.objects.get(email="new-user@example.com")
        self.assertEqual(user.organization, self.org_a)
        self.assertTrue(user.check_password("Str0ng-New-Pass!"))

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatus.ACCEPTED)
        self.assertIsNotNone(invitation.accepted_at)

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

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("invitation_accept"),
                {"token": "valid-token", "password": "alllowercase1"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="new-user@example.com").exists())

    def test_accept_invitation_fails_once_expired(self):
        invitation = InvitationFactory(
            organization=self.org_a, invited_by=self.admin_a, token="valid-token"
        )
        stale = timezone.now() - timedelta(days=999)
        Invitation.objects.filter(pk=invitation.pk).update(created=stale)

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("invitation_accept"),
                {"token": "valid-token", "password": "Str0ng-New-Pass!"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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

    def test_invitation_str_includes_email_and_status(self):
        invitation = InvitationFactory(email="invitee@example.com")

        with self.assertNumQueries(0):
            self.assertEqual(str(invitation), "invitee@example.com (PENDING)")


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class InvitationBulkCreateTests(APITestCase):
    def setUp(self):
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

        with self.assertNumQueries(10):
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

        with self.assertNumQueries(10):
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

        with self.assertNumQueries(5):
            response = self.client.post(
                reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created"], 1)
        self.assertEqual(response.data["skipped"][0]["email"], "DUPE@example.com")
        self.assertEqual(response.data["skipped"][0]["reason"], "duplicate in file")
        mock_send_mail.assert_called_once()

    @patch("core.email.send_mail")
    def test_field_level_rejection_is_skipped_with_its_reason(self, mock_send_mail):
        self.client.force_authenticate(self.admin_a)
        overlong_email = ("a" * 250) + "@example.com"
        upload = build_xlsx_upload(["Email", overlong_email])

        with self.assertNumQueries(2):
            response = self.client.post(
                reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created"], 0)
        self.assertEqual(
            response.data["skipped"][0]["reason"],
            "Ensure this field has no more than 254 characters.",
        )
        mock_send_mail.assert_not_called()

    @patch("core.email.send_mail")
    def test_malformed_rows_are_skipped_without_failing_batch(self, mock_send_mail):
        self.client.force_authenticate(self.admin_a)
        upload = build_xlsx_upload(["Email", "not-an-email", "valid@example.com"])

        with self.assertNumQueries(5):
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
        self.assertEqual(
            reasons["existing@example.com"], "user already exists in organization"
        )
        self.assertEqual(reasons["pending@example.com"], "invitation already pending")
        mock_send_mail.assert_called_once()
        self.assertTrue(Invitation.objects.filter(email="new@example.com").exists())

    def test_cannot_create_invitations_past_the_pending_cap(self):
        self.client.force_authenticate(self.admin_a)
        upload = build_xlsx_upload(["Email", "one@example.com", "two@example.com"])

        with (
            patch("users.api.v1.serializers.MAX_PENDING_INVITATIONS_PER_ORG", 1),
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
            "This organization has too many pending invitations.",
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
