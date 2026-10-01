from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from organizations.api.v1.serializers import OrganizationSummarySerializer
from users.choices import InvitationStatus
from users.constants import MAX_PASSWORD_LENGTH, MAX_PENDING_INVITATIONS_PER_ORG
from users.models import Invitation
from users.services import create_invitation, find_invitation_conflict
from users.validators import validate_password_for_field

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

    # Null for a superuser, who belongs to no organization.
    organization = OrganizationSummarySerializer(read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = ["id", "email", "org_role", "organization"]
        read_only_fields = fields


class OrganizationRoleSerializer(serializers.ModelSerializer):
    """Changes a member's organization role - the only writable field."""

    class Meta:
        model = User
        fields = ["org_role"]


class PasswordChangeSerializer(serializers.Serializer):
    """A signed-in user's own password change: the current password proves
    it's really them, the new one must pass the full password policy."""

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if len(value) > MAX_PASSWORD_LENGTH or not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        validate_password_for_field(
            "new_password", attrs["new_password"], user=self.context["request"].user
        )
        return attrs


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
    """Creates a pending Invitation, and is how invitations are listed.
    `organization`, `invited_by` and `status` are all set server-side - never
    accepted from the client. The token is never returned: it only travels in
    the invitation email, so nobody but the invitee can accept it. `status`
    reads ``EXPIRED`` once a pending link has run out."""

    invited_by_email = serializers.EmailField(
        source="invited_by.email", read_only=True, allow_null=True
    )
    status = serializers.ChoiceField(
        source="current_status", choices=InvitationStatus.choices, read_only=True
    )

    class Meta:
        model = Invitation
        fields = [
            "id",
            "email",
            "organization",
            "invited_by",
            "invited_by_email",
            "status",
            "created",
            "sent_at",
            "accepted_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "invited_by",
            "created",
            "sent_at",
            "accepted_at",
        ]

    def validate_email(self, value):
        conflict = find_invitation_conflict(
            self.context["request"].user.organization, value
        )
        if conflict:
            raise serializers.ValidationError(conflict)
        return value

    def validate(self, attrs):
        org = self.context["request"].user.organization
        pending = Invitation.objects.for_organization(org).pending()
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

        # Accepted, revoked or expired - or the address has an account by now
        # (e.g. it signed up a new organization), which a new user would clash with.
        if (
            invitation.current_status != InvitationStatus.PENDING
            or User.objects.filter(email=invitation.email).exists()
        ):
            raise serializers.ValidationError({"token": INVALID_INVITATION_MESSAGE})

        validate_password_for_field("password", attrs["password"])

        attrs["invitation"] = invitation
        return attrs


class InvitationBulkSkipSerializer(serializers.Serializer):
    email = serializers.CharField(help_text="The row as it appeared in the file.")
    reason = serializers.CharField()


class InvitationBulkResultSerializer(serializers.Serializer):
    """What a bulk upload did: how many invitations were sent, and every row
    that wasn't, with why."""

    created = serializers.IntegerField()
    skipped = InvitationBulkSkipSerializer(many=True)


class TokenPairSerializer(serializers.Serializer):
    """Response shape for endpoints that log a user straight in."""

    access = serializers.CharField()
    refresh = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    """``refresh`` may be omitted when the refresh-token cookie carries it."""

    refresh = serializers.CharField(required=False)


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

        validate_password_for_field("new_password", attrs["new_password"], user=user)

        attrs["user"] = user
        return attrs
