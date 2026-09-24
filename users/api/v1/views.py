from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.permissions import HasActiveSubscription
from users.api.v1.serializers import (
    INVALID_INVITATION_MESSAGE,
    CurrentUserSerializer,
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    LoginSerializer,
    LogoutSerializer,
    OrganizationRoleSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    TokenPairSerializer,
    UserDetailSerializer,
    UserSerializer,
)
from users.api.v1.tokens import (
    clear_refresh_cookie,
    refresh_token_from,
    set_refresh_cookie,
    token_pair_response,
)
from users.choices import InvitationStatus, OrganizationRole
from users.models import Invitation
from users.permissions import IsOrganizationAdmin
from users.services import (
    blacklist_outstanding_tokens,
    bulk_create_invitations,
    parse_invitation_emails,
    refresh_invitation,
)
from users.tasks import send_invitation_email_task, send_password_reset_email_task

User = get_user_model()


def _organization_users(request):
    """Every user - active or not - in the requesting admin's organization;
    anyone outside it is indistinguishable from a missing user."""
    return User.objects.filter(organization_id=request.user.organization_id)


def _get_pending_invitation(request, pk):
    """An invitation in the requester's organization that is still pending;
    one from another organization is a 404, an already-settled one a 400."""
    invitation = get_object_or_404(
        Invitation.objects.for_organization(request.user.organization), pk=pk
    )
    if invitation.status != InvitationStatus.PENDING:
        raise ValidationError({"detail": "This invitation is no longer pending."})
    return invitation


class LoginView(TokenObtainPairView):
    """Email/password → JWT pair, with a tight per-IP rate limit on top of the
    global anon throttle to blunt credential stuffing. Also sets the refresh
    token as an HttpOnly cookie."""

    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        set_refresh_cookie(response, response.data["refresh"])
        return response


class CookieTokenRefreshView(TokenRefreshView):
    """Rotates a refresh token taken from the body or, when the body has
    none, from the HttpOnly cookie - and sets the rotated one back as the
    cookie."""

    def get_serializer(self, *args, **kwargs):
        kwargs["data"] = {"refresh": refresh_token_from(self.request)}
        return super().get_serializer(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        set_refresh_cookie(response, response.data["refresh"])
        return response


class CurrentUserAPIView(generics.RetrieveAPIView):
    """The requesting user's own profile. Deliberately reachable without an
    active subscription, so a client can tell an admin (send to billing) from
    a member (ask your admin) before any gated call returns 402."""

    serializer_class = CurrentUserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserListAPIView(generics.ListAPIView):
    """Lists the active members of the requesting user's own organization -
    e.g. to look up a teammate's id when sharing a project or document. Any
    authenticated org member may list, not just admins, but only an admin's
    response includes ``org_role``/``created`` - a regular member only needs
    an id and email to pick a share target."""

    permission_classes = [IsAuthenticated, HasActiveSubscription]
    filter_backends = [SearchFilter]
    search_fields = ["email"]

    def get_serializer_class(self):
        user = self.request.user
        if user.is_authenticated and user.org_role == OrganizationRole.ADMIN:
            return UserDetailSerializer
        return UserSerializer

    def get_queryset(self):
        organization = self.request.user.organization
        if not organization:
            return User.objects.none()

        return User.objects.filter(organization=organization, is_active=True).order_by(
            "email"
        )


class InvitationListCreateAPIView(generics.ListCreateAPIView):
    """Lists and creates invitations, scoped to the requesting admin's organization."""

    serializer_class = InvitationCreateSerializer
    permission_classes = [IsOrganizationAdmin, HasActiveSubscription]

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

    permission_classes = [IsOrganizationAdmin, HasActiveSubscription]

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
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        result = bulk_create_invitations(
            emails,
            organization=request.user.organization,
            invited_by=request.user,
        )
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

        return token_pair_response(user, status.HTTP_201_CREATED)


class LogoutAPIView(APIView):
    """Blacklists the refresh token - from the body, else the cookie - so it
    can no longer be used, and clears the cookie."""

    permission_classes = [AllowAny]

    @extend_schema(
        request=LogoutSerializer,
        responses={
            205: OpenApiResponse(description="Refresh token blacklisted."),
            400: OpenApiResponse(description="Missing or invalid refresh token."),
        },
    )
    def post(self, request):
        refresh_token = refresh_token_from(request)
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

        response = Response(status=status.HTTP_205_RESET_CONTENT)
        clear_refresh_cookie(response)
        return response


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
            blacklist_outstanding_tokens(user)

        return Response(status=status.HTTP_200_OK)


@extend_schema(
    responses={
        204: OpenApiResponse(description="User deactivated."),
        400: OpenApiResponse(
            description="An admin cannot deactivate their own account."
        ),
        404: OpenApiResponse(description="No such user in your organization."),
    }
)
class DeactivateUserAPIView(generics.DestroyAPIView):
    """Admin-initiated soft-removal of a user within the requesting admin's own
    organization: sets ``is_active=False``, never a hard delete.
    Cross-organization targets are indistinguishable from missing ones.
    """

    permission_classes = [IsOrganizationAdmin, HasActiveSubscription]

    def get_queryset(self):
        return _organization_users(self.request)

    def perform_destroy(self, instance):
        """Soft-delete instead of the default hard ``instance.delete()``; an
        admin may not deactivate their own account."""
        if instance.pk == self.request.user.pk:
            raise ValidationError({"detail": "You cannot deactivate your own account."})

        instance.is_active = False
        instance.save(update_fields=["is_active"])


class PasswordChangeAPIView(APIView):
    """A signed-in user changes their own password. Every refresh token they
    hold is revoked - other devices are signed out - and a fresh pair is
    returned so the current session carries on."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_change"

    @extend_schema(
        request=PasswordChangeSerializer,
        responses={
            200: TokenPairSerializer,
            400: OpenApiResponse(
                description="Wrong current password, or new password rejected."
            ),
        },
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        with transaction.atomic():
            user.set_password(serializer.validated_data["new_password"])
            user.save(update_fields=["password"])
            blacklist_outstanding_tokens(user)

        return token_pair_response(user, status.HTTP_200_OK)


class OrganizationRoleUpdateAPIView(APIView):
    """Promotes a member to admin or demotes an admin to member, within the
    requesting admin's own organization. An admin may not change their own
    role, which also guarantees the organization always keeps an admin."""

    permission_classes = [IsOrganizationAdmin, HasActiveSubscription]

    @extend_schema(
        request=OrganizationRoleSerializer,
        responses={
            200: UserDetailSerializer,
            400: OpenApiResponse(description="Invalid role, or your own account."),
            404: OpenApiResponse(
                description="No such active user in your organization."
            ),
        },
    )
    def patch(self, request, pk):
        if pk == request.user.pk:
            raise ValidationError({"detail": "You cannot change your own role."})

        user = get_object_or_404(
            _organization_users(request).filter(is_active=True), pk=pk
        )
        serializer = OrganizationRoleSerializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(UserDetailSerializer(user).data)


class DeactivatedUserListAPIView(generics.ListAPIView):
    """Deactivated users in the requesting admin's organization - the list
    ``ReactivateUserAPIView`` restores from."""

    serializer_class = UserDetailSerializer
    permission_classes = [IsOrganizationAdmin, HasActiveSubscription]
    filter_backends = [SearchFilter]
    search_fields = ["email"]

    def get_queryset(self):
        return (
            _organization_users(self.request).filter(is_active=False).order_by("email")
        )


class ReactivateUserAPIView(APIView):
    """Reverses a deactivation within the requesting admin's organization.
    An already-active or cross-organization user is a 404."""

    permission_classes = [IsOrganizationAdmin, HasActiveSubscription]

    @extend_schema(request=None, responses={200: UserDetailSerializer})
    def post(self, request, pk):
        user = get_object_or_404(
            _organization_users(request).filter(is_active=False), pk=pk
        )
        user.is_active = True
        user.save(update_fields=["is_active"])

        return Response(UserDetailSerializer(user).data)


class InvitationRevokeAPIView(APIView):
    """Revokes a pending invitation so its link stops working. The record is
    kept (status ``REVOKED``) rather than deleted."""

    permission_classes = [IsOrganizationAdmin, HasActiveSubscription]

    @extend_schema(
        request=None,
        responses={
            204: OpenApiResponse(description="Invitation revoked."),
            400: OpenApiResponse(description="Invitation is no longer pending."),
        },
    )
    def delete(self, request, pk):
        invitation = _get_pending_invitation(request, pk)
        invitation.status = InvitationStatus.REVOKED
        invitation.save(update_fields=["status", "modified"])

        return Response(status=status.HTTP_204_NO_CONTENT)


class InvitationResendAPIView(APIView):
    """Re-sends a pending invitation with a new token and a fresh expiry
    window; the previously emailed link stops working."""

    permission_classes = [IsOrganizationAdmin, HasActiveSubscription]

    @extend_schema(request=None, responses={200: InvitationCreateSerializer})
    def post(self, request, pk):
        invitation = _get_pending_invitation(request, pk)
        refresh_invitation(invitation)
        send_invitation_email_task.delay(invitation.pk)

        return Response(InvitationCreateSerializer(invitation).data)
