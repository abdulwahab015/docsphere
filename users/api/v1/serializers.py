from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from organizations.api.v1.serializers import OrganizationSummarySerializer
from users.choices import InvitationStatus
from users.constants import MAX_PASSWORD_LENGTH, MAX_PENDING_INVITATIONS_PER_ORG
from users.models import Invitation
from users.services import create_invitation

User = get_user_model()

INVALID_INVITATION_MESSAGE = "This invitation link is invalid or has expired."


class UserSerializer(serializers.ModelSerializer):
    """Minimal roster entry visible to every org member - just enough to pick
    a share target. Never accepts writes through this serializer."""

    class Meta:
        model = User
        fields = ["id", "email"]
        read_only_fields = fields


class UserDetailSerializer(UserSerializer):
    """Adds role and join-date - admin-only, for actual user management
    rather than picking a share target."""

    class Meta(UserSerializer.Meta):
        fields = [*UserSerializer.Meta.fields, "org_role", "created"]
        read_only_fields = fields


class CurrentUserSerializer(serializers.ModelSerializer):
    """The requesting user's own identity, role and organization - what a
    client needs after login to decide which screens to offer."""

    organization = OrganizationSummarySerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "org_role", "organization"]
        read_only_fields = fields


class LoginSerializer(TokenObtainPairSerializer):
    """Adds a password-length ceiling before the (unvalidated) auth check, so an
    oversized string can't reach the password hasher."""

    def validate(self, attrs):
        if len(attrs.get("password") or "") > MAX_PASSWORD_LENGTH:
            raise AuthenticationFailed(
                "No active account found with the given credentials",
                "no_active_account",
            )
        return super().validate(attrs)


class InvitationCreateSerializer(serializers.ModelSerializer):
    """Creates a pending Invitation. `organization`, `invited_by`, `token`, and
    `status` are all set server-side — never accepted from the client."""

    class Meta:
        model = Invitation
        fields = [
            "id",
            "email",
            "organization",
            "invited_by",
            "token",
            "status",
            "created",
            "accepted_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "invited_by",
            "token",
            "status",
            "created",
            "accepted_at",
        ]

    def validate_email(self, value):
        org = self.context["request"].user.organization
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        if (
            Invitation.objects.for_organization(org)
            .filter(email=value, status=InvitationStatus.PENDING)
            .exists()
        ):
            raise serializers.ValidationError(
                "This email already has a pending invitation."
            )
        return value

    def validate(self, attrs):
        org = self.context["request"].user.organization
        pending = Invitation.objects.for_organization(org).filter(
            status=InvitationStatus.PENDING
        )
        if pending.count() >= MAX_PENDING_INVITATIONS_PER_ORG:
            raise serializers.ValidationError(
                "This organization has too many pending invitations."
            )
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        return create_invitation(
            organization=user.organization,
            invited_by=user,
            email=validated_data["email"],
        )


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            invitation = Invitation.objects.select_related("organization").get(
                token=attrs["token"]
            )
        except Invitation.DoesNotExist:
            raise serializers.ValidationError(
                {"token": INVALID_INVITATION_MESSAGE}
            ) from None

        if invitation.status != InvitationStatus.PENDING:
            raise serializers.ValidationError({"token": INVALID_INVITATION_MESSAGE})

        if timezone.now() - invitation.created > settings.INVITATION_EXPIRY:
            raise serializers.ValidationError({"token": INVALID_INVITATION_MESSAGE})

        validate_password(attrs["password"])

        attrs["invitation"] = invitation
        return attrs


class TokenPairSerializer(serializers.Serializer):
    """Response shape for endpoints that log a user straight in."""

    access = serializers.CharField()
    refresh = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
        except Exception:
            raise serializers.ValidationError("Invalid reset link.") from None

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.") from None

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError("Invalid or expired reset link.")

        validate_password(attrs["new_password"], user=user)

        attrs["user"] = user
        return attrs
