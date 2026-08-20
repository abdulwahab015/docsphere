from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from users.permissions import IsOrgAdmin
from users.serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
)
from users.services import send_password_reset_email


class LogoutView(APIView):
    """Blacklists the given refresh token so it can no longer be used."""

    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            RefreshToken(refresh_token).blacklist()
        except TokenError:
            return Response(
                {"detail": "Token is invalid or already blacklisted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_205_RESET_CONTENT)


class PasswordResetRequestView(APIView):
    """Sends a password-reset email if the address matches an existing user.

    Always returns 200 regardless of whether the email matched, so the
    endpoint can't be used to enumerate registered accounts.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = (
            get_user_model()
            .objects.filter(email=serializer.validated_data["email"])
            .first()
        )
        if user is not None:
            send_password_reset_email(user)

        return Response(status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """Validates the reset token and sets the user's new password."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        return Response(status=status.HTTP_200_OK)


class DeactivateUserView(APIView):
    """Admin-only soft-removal of a user within the requesting admin's own
    organization."""

    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def delete(self, request, pk):
        target = get_object_or_404(
            get_user_model(), pk=pk, organization=request.user.organization
        )

        if target.id == request.user.id:
            return Response(
                {"detail": "You cannot deactivate your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target.is_active = False
        target.save(update_fields=["is_active"])

        return Response(status=status.HTTP_204_NO_CONTENT)
