from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from organizations.models import Organization

User = get_user_model()


class OrganizationSerializer(serializers.ModelSerializer):
    """``billing_email`` uniqueness is checked here so a collision returns 400
    rather than surfacing as an IntegrityError."""

    class Meta:
        model = Organization
        fields = ["id", "name", "billing_email", "created", "modified"]
        read_only_fields = ["id", "created", "modified"]

    def validate_billing_email(self, value):
        clashes = Organization.objects.filter(billing_email=value).exclude(
            pk=self.instance.pk
        )
        if clashes.exists():
            raise serializers.ValidationError(
                "An organization with this billing email already exists."
            )
        return value


class OrganizationSignupSerializer(serializers.Serializer):
    """Input for creating an Organization together with its first admin User."""

    name = serializers.CharField(max_length=100)
    billing_email = serializers.EmailField(required=False, allow_null=True)
    admin_email = serializers.EmailField()
    admin_password = serializers.CharField(write_only=True)

    def validate_billing_email(self, value):
        if Organization.objects.filter(billing_email=value).exists():
            raise serializers.ValidationError(
                "An organization with this billing email already exists."
            )
        return value

    def validate_admin_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        validate_password(attrs["admin_password"])
        return attrs
