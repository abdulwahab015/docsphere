from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from openpyxl import Workbook
from rest_framework import status
from rest_framework.test import APITestCase

from organizations.models import Organization
from users.choices import InvitationStatus, OrganizationRole
from users.models import Invitation

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
        self.user = User.objects.create_user(
            email="member@example.com", password=self.password
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

    def test_login_fails_with_wrong_password(self):
        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("auth_login"),
                {"email": self.user.email, "password": "wrong-password"},
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_new_access_token(self):
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

        reuse_response = self.client.post(
            reverse("auth_refresh"), {"refresh": refresh_token}
        )
        self.assertEqual(reuse_response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class PasswordResetTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="member@example.com", password="Old-Pass-123!"
        )

    @patch("users.tasks.send_mail")
    def test_password_reset_request_sends_email(self, mock_send_mail):
        with self.assertNumQueries(3):
            response = self.client.post(
                reverse("auth_password_reset"), {"email": self.user.email}
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_mail.assert_called_once()

    @patch("users.tasks.send_mail")
    def test_password_reset_request_with_unknown_email_still_returns_200(
        self, mock_send_mail
    ):
        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("auth_password_reset"), {"email": "nobody@example.com"}
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_mail.assert_not_called()

    def test_password_reset_confirm_changes_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        new_password = "New-Strong-Pass!456"

        with self.assertNumQueries(2):
            response = self.client.post(
                reverse("auth_password_reset_confirm"),
                {"uid": uid, "token": token, "new_password": new_password},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

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


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class InvitationTests(APITestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name="Org A")
        self.org_b = Organization.objects.create(name="Org B")

        self.admin_a = User.objects.create_user(
            email="admin-a@example.com",
            password="Admin-Pass-123!",
            organization=self.org_a,
            org_role=OrganizationRole.ADMIN,
        )
        self.member_a = User.objects.create_user(
            email="member-a@example.com",
            password="Member-Pass-123!",
            organization=self.org_a,
            org_role=OrganizationRole.MEMBER,
        )
        self.admin_b = User.objects.create_user(
            email="admin-b@example.com",
            password="Admin-Pass-123!",
            organization=self.org_b,
            org_role=OrganizationRole.ADMIN,
        )

    @patch("users.tasks.send_mail")
    def test_admin_can_create_invitation_for_own_organization(self, mock_send_mail):
        self.client.force_authenticate(self.admin_a)

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

        response = self.client.post(
            reverse("invitation_list_create"), {"email": "invitee@example.com"}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            Invitation.objects.filter(email="invitee@example.com").exists()
        )

    def test_admin_cannot_see_invitations_outside_own_organization(self):
        Invitation.objects.create(
            organization=self.org_b,
            invited_by=self.admin_b,
            email="other-org-invitee@example.com",
            token="org-b-token",
        )

        self.client.force_authenticate(self.admin_a)
        response = self.client.get(reverse("invitation_list_create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = [item["email"] for item in response.data]
        self.assertNotIn("other-org-invitee@example.com", emails)

    def test_accept_invitation_creates_user_and_logs_in(self):
        invitation = Invitation.objects.create(
            organization=self.org_a,
            invited_by=self.admin_a,
            email="new-user@example.com",
            token="valid-token",
        )

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
        Invitation.objects.create(
            organization=self.org_a,
            invited_by=self.admin_a,
            email="new-user@example.com",
            token="valid-token",
            status=InvitationStatus.ACCEPTED,
        )

        response = self.client.post(
            reverse("invitation_accept"),
            {"token": "valid-token", "password": "Str0ng-New-Pass!"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_invitation_with_invalid_token_fails(self):
        response = self.client.post(
            reverse("invitation_accept"),
            {"token": "nonexistent-token", "password": "Str0ng-New-Pass!"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class InvitationBulkCreateTests(APITestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name="Org A")

        self.admin_a = User.objects.create_user(
            email="admin-a@example.com",
            password="Admin-Pass-123!",
            organization=self.org_a,
            org_role=OrganizationRole.ADMIN,
        )
        self.member_a = User.objects.create_user(
            email="member-a@example.com",
            password="Member-Pass-123!",
            organization=self.org_a,
            org_role=OrganizationRole.MEMBER,
        )

    @patch("users.tasks.send_mail")
    def test_valid_file_creates_invitations_and_sends_emails(self, mock_send_mail):
        self.client.force_authenticate(self.admin_a)
        upload = build_xlsx_upload(["Email", "one@example.com", "two@example.com"])

        response = self.client.post(
            reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created"], 2)
        self.assertEqual(response.data["skipped"], [])
        self.assertEqual(mock_send_mail.call_count, 2)
        self.assertTrue(Invitation.objects.filter(email="one@example.com").exists())
        self.assertTrue(Invitation.objects.filter(email="two@example.com").exists())

    @patch("users.tasks.send_mail")
    def test_malformed_rows_are_skipped_without_failing_batch(self, mock_send_mail):
        self.client.force_authenticate(self.admin_a)
        upload = build_xlsx_upload(["Email", "not-an-email", "valid@example.com"])

        response = self.client.post(
            reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created"], 1)
        self.assertEqual(len(response.data["skipped"]), 1)
        self.assertEqual(response.data["skipped"][0]["email"], "not-an-email")
        self.assertEqual(response.data["skipped"][0]["reason"], "invalid email")
        mock_send_mail.assert_called_once()

    @patch("users.tasks.send_mail")
    def test_existing_user_and_pending_invitation_are_skipped(self, mock_send_mail):
        User.objects.create_user(
            email="existing@example.com",
            password="Existing-Pass-1!",
            organization=self.org_a,
        )
        Invitation.objects.create(
            organization=self.org_a,
            invited_by=self.admin_a,
            email="pending@example.com",
            token="already-pending-token",
        )
        self.client.force_authenticate(self.admin_a)
        upload = build_xlsx_upload(
            ["Email", "existing@example.com", "pending@example.com", "new@example.com"]
        )

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

    def test_non_admin_cannot_bulk_create_invitations(self):
        self.client.force_authenticate(self.member_a)
        upload = build_xlsx_upload(["Email", "someone@example.com"])

        response = self.client.post(
            reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            Invitation.objects.filter(email="someone@example.com").exists()
        )
