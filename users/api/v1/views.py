from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiResponse,
    PolymorphicProxySerializer,
    extend_schema,
)
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from audit.choices import AuditVerb
from audit.models import AuditEvent
from core.permissions import HasActiveSubscription
from users.api.v1.serializers import (
    INVALID_INVITATION_MESSAGE,
    CurrentUserSerializer,
    EmailChangeConfirmSerializer,
    EmailChangeRequestSerializer,
    EmailVerificationSerializer,
    InvitationAcceptSerializer,
    InvitationBulkResultSerializer,
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
from users.permissions import HasVerifiedEmail, IsOrganizationAdmin
from users.services import (
    EMAIL_IN_USE_MESSAGE,
    blacklist_outstanding_tokens,
    bulk_create_invitations,
    find_invitation_conflict,
    is_email_in_use,
    lock_organization_for_admin_change,
    parse_invitation_emails,
    refresh_invitation,
)
from users.tasks import (
    send_email_change_link_task,
    send_email_changed_notice_task,
    send_invitation_email_task,
    send_password_reset_email_task,
    send_verification_email_task,
)

User = get_user_model()


def _organization_users(request):
    """Every user - active or not - in the requesting admin's organization;
    anyone outside it is indistinguishable from a missing user."""
    return User.objects.filter(organization_id=request.user.organization_id)


def _get_pending_invitation(request, pk):
    """An invitation in the requester's organization that is still pending;
    one from another organization is a 404, an already-settled one a 400."""
    invitation = get_object_or_404(
        Invitation.objects.for_organization(request.user.organization).select_related(
            "invited_by"
        ),
        pk=pk,
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


class CurrentUserAPIView(generics.RetrieveUpdateAPIView):
    """The requesting user's own profile, and changing their name (the only
    part they may edit). Deliberately reachable without an active
    subscription, so a client can tell an admin (send to billing) from a
    member (ask your admin) before any gated call returns 402 - and readable
    before the email is verified, which is how a client learns to ask for
    that."""

    serializer_class = CurrentUserSerializer
    # Partial updates only: a PUT would have to resend read-only fields.
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAuthenticated(), HasVerifiedEmail()]

    def get_object(self):
        return self.request.user


class EmailVerificationResendAPIView(APIView):
    """Emails a signed-in user who hasn't verified their address a new
    verification link. Earlier links keep working until they expire."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_verification"

    @extend_schema(
        request=None,
        responses={
            204: OpenApiResponse(description="A new link was sent."),
            400: OpenApiResponse(description="The address is already verified."),
        },
    )
    def post(self, request):
        if request.user.email_verified:
            raise ValidationError({"detail": "Your email address is already verified."})

        send_verification_email_task.delay(request.user.pk)

        return Response(status=status.HTTP_204_NO_CONTENT)


class EmailVerificationConfirmAPIView(APIView):
    """Marks an address verified from the link emailed to it. Works signed in
    or not - the link may be opened on another device - and following it
    again changes nothing."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_verification"

    @extend_schema(
        request=EmailVerificationSerializer,
        responses={
            204: OpenApiResponse(description="The address is verified."),
            400: OpenApiResponse(description="Invalid or expired link."),
        },
    )
    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        if not user.email_verified:
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified_at"])

        return Response(status=status.HTTP_204_NO_CONTENT)


class EmailChangeRequestAPIView(APIView):
    """A signed-in user asks to sign in with another address: a link to
    confirm it is emailed to the new address, and nothing changes until it's
    followed."""

    permission_classes = [IsAuthenticated, HasVerifiedEmail]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_change"

    @extend_schema(
        request=EmailChangeRequestSerializer,
        responses={
            204: OpenApiResponse(description="A link was sent to the new address."),
            400: OpenApiResponse(
                description="Wrong current password, or the address is your own "
                "or already in use."
            ),
        },
    )
    def post(self, request):
        serializer = EmailChangeRequestSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        send_email_change_link_task.delay(
            request.user.pk, serializer.validated_data["new_email"]
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class EmailChangeConfirmAPIView(APIView):
    """Moves an account to the address its link was emailed to. The address
    is checked again - someone may have taken it since the link was sent -
    every session is signed out, and the old address is told."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_change"

    @extend_schema(
        request=EmailChangeConfirmSerializer,
        responses={
            204: OpenApiResponse(description="The email changed; log in again."),
            400: OpenApiResponse(
                description="Invalid or expired link, or the address is in use."
            ),
        },
    )
    def post(self, request):
        serializer = EmailChangeConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        old_email = user.email
        new_email = serializer.validated_data["new_email"]

        with transaction.atomic():
            if is_email_in_use(new_email):
                raise ValidationError({"detail": EMAIL_IN_USE_MESSAGE})

            User.objects.release_email(new_email)
            user.email = new_email
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email", "email_verified_at"])
            blacklist_outstanding_tokens(user)

        send_email_changed_notice_task.delay(old_email, user.email)

        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    # The serializer depends on the caller's role, so document both shapes:
    # admins also get ``org_role`` and ``created``.
    responses=PolymorphicProxySerializer(
        component_name="RosterUser",
        serializers=[UserDetailSerializer, UserSerializer],
        resource_type_field_name=None,
        many=True,
    )
)
class UserListAPIView(generics.ListAPIView):
    """Lists the active members of the requesting user's own organization -
    e.g. to look up a teammate's id when sharing a project or document. Any
    authenticated org member may list, not just admins, but only an admin's
    response includes ``org_role``/``created`` - a regular member only needs
    an id and email to pick a share target."""

    permission_classes = [IsAuthenticated, HasVerifiedEmail, HasActiveSubscription]
    filter_backends = [SearchFilter]
    search_fields = ["email", "name"]

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
    permission_classes = [IsOrganizationAdmin, HasVerifiedEmail, HasActiveSubscription]

    def get_queryset(self):
        return (
            Invitation.objects.for_organization(self.request.user.organization)
            .select_related("invited_by")
            .order_by("-created")
        )

    def perform_create(self, serializer):
        invitation = serializer.save()
        send_invitation_email_task.delay(invitation.pk)


class InvitationBulkCreateAPIView(APIView):
    """Creates invitations in bulk from an uploaded .xlsx file of email
    addresses, scoped to the requesting admin's organization."""

    permission_classes = [IsOrganizationAdmin, HasVerifiedEmail, HasActiveSubscription]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
                "required": ["file"],
            }
        },
        responses={
            201: InvitationBulkResultSerializer,
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
        summary = {"created": len(result["created"]), "skipped": result["skipped"]}
        return Response(
            InvitationBulkResultSerializer(summary).data,
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
            if invitation.current_status != InvitationStatus.PENDING:
                return Response(
                    {"token": INVALID_INVITATION_MESSAGE},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            User.objects.release_email(invitation.email)
            # The invitation's link was emailed to this address, so following
            # it proves the address is theirs.
            user = User.objects.create_user(
                email=invitation.email,
                password=password,
                name=serializer.validated_data["name"],
                organization=invitation.organization,
                email_verified_at=timezone.now(),
            )

            invitation.status = InvitationStatus.ACCEPTED
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=["status", "accepted_at"])
            AuditEvent.objects.record(
                user, AuditVerb.INVITATION_ACCEPTED, email=invitation.email
            )

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
    """Sends a password-reset email if the address matches an active user -
    a deactivated one couldn't log in with a new password anyway.

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

        matching_users = User.objects.filter(
            email=serializer.validated_data["email"], is_active=True
        )
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

    permission_classes = [IsOrganizationAdmin, HasVerifiedEmail, HasActiveSubscription]

    def get_queryset(self):
        return _organization_users(self.request)

    def perform_destroy(self, instance):
        """Soft-delete instead of the default hard ``instance.delete()``; an
        admin may not deactivate their own account."""
        if instance.pk == self.request.user.pk:
            raise ValidationError({"detail": "You cannot deactivate your own account."})

        with transaction.atomic():
            lock_organization_for_admin_change(self.request.user)
            instance.is_active = False
            instance.save(update_fields=["is_active"])
            AuditEvent.objects.record(
                self.request.user, AuditVerb.MEMBER_DEACTIVATED, target_user=instance
            )


class PasswordChangeAPIView(APIView):
    """A signed-in user changes their own password. Every refresh token they
    hold is revoked - other devices are signed out - and a fresh pair is
    returned so the current session carries on."""

    permission_classes = [IsAuthenticated, HasVerifiedEmail]
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
    role, and changes are made one at a time by admins who still are one, so
    the organization always keeps an admin."""

    permission_classes = [IsOrganizationAdmin, HasVerifiedEmail, HasActiveSubscription]

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
        previous_role = user.org_role
        with transaction.atomic():
            lock_organization_for_admin_change(request.user)
            serializer.save()
            if user.org_role != previous_role:
                AuditEvent.objects.record(
                    request.user,
                    AuditVerb.ROLE_CHANGED,
                    target_user=user,
                    role=user.org_role,
                    previous_role=previous_role,
                )

        return Response(UserDetailSerializer(user).data)


class DeactivatedUserListAPIView(generics.ListAPIView):
    """Deactivated users in the requesting admin's organization - the list
    ``ReactivateUserAPIView`` restores from."""

    serializer_class = UserDetailSerializer
    permission_classes = [IsOrganizationAdmin, HasVerifiedEmail, HasActiveSubscription]
    filter_backends = [SearchFilter]
    search_fields = ["email", "name"]

    def get_queryset(self):
        return (
            _organization_users(self.request).filter(is_active=False).order_by("email")
        )


class ReactivateUserAPIView(APIView):
    """Reverses a deactivation within the requesting admin's organization.
    An already-active or cross-organization user is a 404."""

    permission_classes = [IsOrganizationAdmin, HasVerifiedEmail, HasActiveSubscription]

    @extend_schema(request=None, responses={200: UserDetailSerializer})
    def post(self, request, pk):
        user = get_object_or_404(
            _organization_users(request).filter(is_active=False), pk=pk
        )
        with transaction.atomic():
            user.is_active = True
            user.save(update_fields=["is_active"])
            AuditEvent.objects.record(
                request.user, AuditVerb.MEMBER_REACTIVATED, target_user=user
            )

        return Response(UserDetailSerializer(user).data)


class InvitationRevokeAPIView(APIView):
    """Revokes a pending invitation so its link stops working. The record is
    kept (status ``REVOKED``) rather than deleted."""

    permission_classes = [IsOrganizationAdmin, HasVerifiedEmail, HasActiveSubscription]

    @extend_schema(
        request=None,
        responses={
            204: OpenApiResponse(description="Invitation revoked."),
            400: OpenApiResponse(description="Invitation is no longer pending."),
        },
    )
    def delete(self, request, pk):
        invitation = _get_pending_invitation(request, pk)
        with transaction.atomic():
            invitation.status = InvitationStatus.REVOKED
            invitation.save(update_fields=["status", "modified"])
            AuditEvent.objects.record(
                request.user, AuditVerb.INVITATION_REVOKED, email=invitation.email
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class InvitationResendAPIView(APIView):
    """Re-sends a pending invitation with a new token and a fresh expiry
    window; the previously emailed link stops working. An expired invitation
    can be resent too - unless the address has joined, or been sent a newer
    invitation, since."""

    permission_classes = [IsOrganizationAdmin, HasVerifiedEmail, HasActiveSubscription]

    @extend_schema(
        request=None,
        responses={
            200: InvitationCreateSerializer,
            400: OpenApiResponse(
                description="No longer pending, the address has an account, "
                "or it has a newer pending invitation."
            ),
        },
    )
    def post(self, request, pk):
        invitation = _get_pending_invitation(request, pk)
        conflict = find_invitation_conflict(
            request.user.organization, invitation.email, renewing=invitation
        )
        if conflict:
            raise ValidationError({"detail": conflict})

        with transaction.atomic():
            refresh_invitation(invitation)
            AuditEvent.objects.record(
                request.user, AuditVerb.INVITATION_RESENT, email=invitation.email
            )
        send_invitation_email_task.delay(invitation.pk)

        return Response(InvitationCreateSerializer(invitation).data)
