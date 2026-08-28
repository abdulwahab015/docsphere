from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from openpyxl.utils.exceptions import InvalidFileException
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from users.choices import InvitationStatus
from users.models import Invitation
from users.permissions import IsOrganizationAdmin
from users.serializers import (
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
)
from users.services import (
    BulkInviteLimitExceeded,
    bulk_create_invitations,
    parse_invitation_emails,
)
from users.tasks import send_invitation_email_task, send_password_reset_email_task

User = get_user_model()


class InvitationListCreateView(generics.ListCreateAPIView):
    """Lists and creates invitations, scoped to the requesting admin's organization."""

    serializer_class = InvitationCreateSerializer
    permission_classes = [IsAuthenticated, IsOrganizationAdmin]

    def get_queryset(self):
        return Invitation.objects.for_organization(self.request.user.organization)

    def perform_create(self, serializer):
        invitation = serializer.save()
        send_invitation_email_task.delay(invitation.pk)


class InvitationBulkCreateView(APIView):
    """Creates invitations in bulk from an uploaded .xlsx file of email
    addresses, scoped to the requesting admin's organization."""

    permission_classes = [IsAuthenticated, IsOrganizationAdmin]
    parser_classes = [MultiPartParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response(
                {"detail": "file is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            emails = parse_invitation_emails(upload)
        except InvalidFileException:
            return Response(
                {"detail": "file must be a valid .xlsx workbook."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except BulkInviteLimitExceeded as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        result = bulk_create_invitations(emails, request)
        return Response(
            {"created": len(result["created"]), "skipped": result["skipped"]},
            status=status.HTTP_201_CREATED,
        )


class InvitationAcceptView(APIView):
    """Creates the invitee's User account from a valid, pending invitation token
    and logs them in immediately with a JWT pair."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = serializer.validated_data["invitation"]

        user = User.objects.create_user(
            email=invitation.email,
            password=serializer.validated_data["password"],
            organization=invitation.organization,
        )

        invitation.status = InvitationStatus.ACCEPTED
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["status", "accepted_at"])

        refresh = RefreshToken.for_user(user)
        return Response(
            {"access": str(refresh.access_token), "refresh": str(refresh)},
            status=status.HTTP_201_CREATED,
        )


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

        matching_users = User.objects.filter(email=serializer.validated_data["email"])
        if matching_users.exists():
            send_password_reset_email_task.delay(matching_users.get().pk)

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

    permission_classes = [IsAuthenticated, IsOrganizationAdmin]

    def delete(self, request, pk):
        target = get_object_or_404(User, pk=pk, organization=request.user.organization)

        if target.id == request.user.id:
            return Response(
                {"detail": "You cannot deactivate your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target.is_active = False
        target.save(update_fields=["is_active"])

        return Response(status=status.HTTP_204_NO_CONTENT)
