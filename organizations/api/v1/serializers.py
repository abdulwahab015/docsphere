from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from organizations.models import Organization
from subscriptions.utils import get_period_end

User = get_user_model()


class ActiveSubscriptionSerializer(serializers.Serializer):
    """Read-only summary of a dj-stripe Subscription."""

    id = serializers.CharField()
    status = serializers.CharField()
    interval = serializers.SerializerMethodField()
    current_period_end = serializers.SerializerMethodField()
    cancel_at_period_end = serializers.SerializerMethodField()

    def get_cancel_at_period_end(self, subscription) -> bool:
        return bool(subscription.stripe_data.get("cancel_at_period_end"))

    def get_interval(self, subscription) -> str | None:
        return (subscription.stripe_data.get("plan") or {}).get("interval")

    def get_current_period_end(self, subscription) -> datetime | None:
        return get_period_end(subscription)


class OrganizationSummarySerializer(serializers.ModelSerializer):
    """The slice of an organization any member may see about their own org:
    enough for a client to label it and to route an unpaid org to billing
    before hitting a 402."""

    has_active_subscription = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "has_active_subscription"]
        read_only_fields = fields

    def get_has_active_subscription(self, organization) -> bool:
        return bool(organization.active_subscription)


class OrganizationSerializer(serializers.ModelSerializer):
    """``billing_email`` uniqueness is checked here so a collision returns 400
    rather than surfacing as an IntegrityError."""

    active_subscription = ActiveSubscriptionSerializer(read_only=True)

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "billing_email",
            "active_subscription",
            "created",
            "modified",
        ]
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
