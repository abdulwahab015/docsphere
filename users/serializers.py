import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from users.choices import InvitationStatus
from users.models import Invitation

User = get_user_model()


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

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["organization"] = request.user.organization
        validated_data["invited_by"] = request.user
        validated_data["token"] = secrets.token_urlsafe(32)

        return super().create(validated_data)


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
                {"token": "Invalid invitation token."}
            ) from None

        if invitation.status != InvitationStatus.PENDING:
            raise serializers.ValidationError(
                {"token": "This invitation is no longer valid."}
            )

        validate_password(attrs["password"])

        attrs["invitation"] = invitation
        return attrs


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
            raise serializers.ValidationError("Invalid reset link.")

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError("Invalid or expired reset link.")

        validate_password(attrs["new_password"], user=user)

        attrs["user"] = user
        return attrs
