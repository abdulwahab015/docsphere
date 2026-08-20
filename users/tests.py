from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

from organizations.models import Organization
from users.choices import OrganizationRole

User = get_user_model()


class JWTAuthTests(APITestCase):
    def setUp(self):
        self.password = "S0me-Strong-Pass!"
        self.user = User.objects.create_user(
            email="member@example.com", password=self.password
        )

    def test_login_succeeds_with_correct_credentials(self):
        response = self.client.post(
            reverse("auth-login"),
            {"email": self.user.email, "password": self.password},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_fails_with_wrong_password(self):
        response = self.client.post(
            reverse("auth-login"),
            {"email": self.user.email, "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_new_access_token(self):
        login_response = self.client.post(
            reverse("auth-login"),
            {"email": self.user.email, "password": self.password},
        )
        refresh_token = login_response.data["refresh"]

        response = self.client.post(reverse("auth-refresh"), {"refresh": refresh_token})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_logout_blacklists_refresh_token(self):
        login_response = self.client.post(
            reverse("auth-login"),
            {"email": self.user.email, "password": self.password},
        )
        refresh_token = login_response.data["refresh"]

        logout_response = self.client.post(
            reverse("auth-logout"), {"refresh": refresh_token}
        )
        self.assertEqual(logout_response.status_code, status.HTTP_205_RESET_CONTENT)

        reuse_response = self.client.post(
            reverse("auth-refresh"), {"refresh": refresh_token}
        )
        self.assertEqual(reuse_response.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordResetTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="member@example.com", password="Old-Pass-123!"
        )

    @patch("users.services.send_mail")
    def test_password_reset_request_sends_email(self, mock_send_mail):
        response = self.client.post(
            reverse("auth-password-reset"), {"email": self.user.email}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_mail.assert_called_once()

    @patch("users.services.send_mail")
    def test_password_reset_request_with_unknown_email_still_returns_200(
        self, mock_send_mail
    ):
        response = self.client.post(
            reverse("auth-password-reset"), {"email": "nobody@example.com"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_mail.assert_not_called()

    def test_password_reset_confirm_changes_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        new_password = "New-Strong-Pass!456"

        response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {"uid": uid, "token": token, "new_password": new_password},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    def test_password_reset_confirm_fails_with_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": uid,
                "token": "invalid-token",
                "new_password": "New-Strong-Pass!456",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DeactivateUserTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Acme")
        self.other_org = Organization.objects.create(name="Globex")

        self.admin_password = "Admin-Pass-123!"
        self.admin = User.objects.create_user(
            email="admin@acme.example.com",
            password=self.admin_password,
            organization=self.org,
            org_role=OrganizationRole.ADMIN,
        )
        self.member = User.objects.create_user(
            email="member@acme.example.com",
            password="Member-Pass-123!",
            organization=self.org,
            org_role=OrganizationRole.MEMBER,
        )
        self.other_org_user = User.objects.create_user(
            email="member@globex.example.com",
            password="Member-Pass-123!",
            organization=self.other_org,
            org_role=OrganizationRole.MEMBER,
        )

    def _deactivate_url(self, user):
        return reverse("user-deactivate", kwargs={"pk": user.pk})

    def test_admin_deactivates_user_in_own_org(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.delete(self._deactivate_url(self.member))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)

    def test_admin_cannot_deactivate_user_in_different_org(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.delete(self._deactivate_url(self.other_org_user))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.other_org_user.refresh_from_db()
        self.assertTrue(self.other_org_user.is_active)

    def test_admin_cannot_deactivate_self(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.delete(self._deactivate_url(self.admin))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.delete(self._deactivate_url(self.other_org_user))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deactivated_user_cannot_obtain_new_jwt(self):
        self.client.force_authenticate(user=self.admin)
        self.client.delete(self._deactivate_url(self.member))
        self.client.force_authenticate(user=None)

        response = self.client.post(
            reverse("auth-login"),
            {"email": self.member.email, "password": "Member-Pass-123!"},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
