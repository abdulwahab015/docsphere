from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from openpyxl.utils.exceptions import InvalidFileException
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from users.api.v1.serializers import (
    INVALID_INVITATION_MESSAGE,
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    TokenPairSerializer,
)
from users.choices import InvitationStatus
from users.models import Invitation
from users.permissions import IsOrganizationAdmin
from users.services import (
    BulkInviteLimitExceeded,
    bulk_create_invitations,
    parse_invitation_emails,
)
from users.tasks import send_invitation_email_task, send_password_reset_email_task

User = get_user_model()


class LoginView(TokenObtainPairView):
    """Email/password → JWT pair, with a tight per-IP rate limit on top of the
    global anon throttle to blunt credential stuffing."""

    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class InvitationListCreateAPIView(generics.ListCreateAPIView):
    """Lists and creates invitations, scoped to the requesting admin's organization."""

    serializer_class = InvitationCreateSerializer
    permission_classes = [IsOrganizationAdmin]

    def get_queryset(self):
        return Invitation.objects.for_organization(
            self.request.user.organization
        ).order_by("-created")

    def perform_create(self, serializer):
        invitation = serializer.save()
        send_invitation_email_task.delay(invitation.pk)


class InvitationBulkCreateAPIView(APIView):
    """Creates invitations in bulk from an uploaded .xlsx file of email
    addresses, scoped to the requesting admin's organization."""

    permission_classes = [IsOrganizationAdmin]
    parser_classes = [MultiPartParser]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
                "required": ["file"],
            }
        },
        responses={
            201: OpenApiResponse(description="Summary of created/skipped rows."),
            400: OpenApiResponse(
                description="Missing file, invalid .xlsx, or row-count cap exceeded."
            ),
        },
    )
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


class InvitationAcceptAPIView(APIView):
    """Creates the invitee's User account from a valid, pending invitation token
    and logs them in immediately with a JWT pair."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "invite_accept"

    @extend_schema(
        request=InvitationAcceptSerializer,
        responses={201: TokenPairSerializer},
    )
    def post(self, request):
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data["password"]
        invitation_id = serializer.validated_data["invitation"].pk

        with transaction.atomic():
            invitation = (
                Invitation.objects.select_for_update()
                .select_related("organization")
                .get(pk=invitation_id)
            )
            if invitation.status != InvitationStatus.PENDING:
                return Response(
                    {"token": INVALID_INVITATION_MESSAGE},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = User.objects.create_user(
                email=invitation.email,
                password=password,
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


class LogoutAPIView(APIView):
    """Blacklists the given refresh token so it can no longer be used."""

    permission_classes = [AllowAny]

    @extend_schema(
        request=LogoutSerializer,
        responses={
            205: OpenApiResponse(description="Refresh token blacklisted."),
            400: OpenApiResponse(description="Missing or invalid refresh token."),
        },
    )
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


class PasswordResetRequestAPIView(APIView):
    """Sends a password-reset email if the address matches an existing user.

    Always returns 200 regardless of whether the email matched, so the
    endpoint can't be used to enumerate registered accounts.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={200: OpenApiResponse(description="Always returned, match or not.")},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        matching_users = User.objects.filter(email=serializer.validated_data["email"])
        if matching_users.exists():
            send_password_reset_email_task.delay(matching_users.get().pk)

        return Response(status=status.HTTP_200_OK)


class PasswordResetConfirmAPIView(APIView):
    """Validates the reset token and sets the user's new password."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(description="Password changed."),
            400: OpenApiResponse(description="Invalid or expired reset link."),
        },
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        with transaction.atomic():
            user.set_password(serializer.validated_data["new_password"])
            user.save(update_fields=["password"])

            for token in OutstandingToken.objects.filter(user=user):
                BlacklistedToken.objects.get_or_create(token=token)

        return Response(status=status.HTTP_200_OK)
