from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

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
