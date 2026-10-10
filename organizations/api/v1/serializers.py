from datetime import datetime

from django.contrib.auth import get_user_model
from rest_framework import serializers

from organizations.models import Organization
from organizations.validators import validate_unique_billing_email
from subscriptions.utils import cancels_at_period_end, get_period_end, is_past_due
from users.constants import MAX_NAME_LENGTH
from users.validators import validate_password_for_field

User = get_user_model()

REQUIRE_TWO_FACTOR_WITHOUT_IT_MESSAGE = (
    "Turn on two-factor sign-in for your own account before requiring it."
)


class ActiveSubscriptionSerializer(serializers.Serializer):
    """Read-only summary of a dj-stripe Subscription."""

    id = serializers.CharField()
    status = serializers.CharField()
    interval = serializers.SerializerMethodField()
    current_period_end = serializers.SerializerMethodField()
    cancel_at_period_end = serializers.SerializerMethodField()

    def get_cancel_at_period_end(self, subscription) -> bool:
        return cancels_at_period_end(subscription)

    def get_interval(self, subscription) -> str | None:
        return (subscription.stripe_data.get("plan") or {}).get("interval")

    def get_current_period_end(self, subscription) -> datetime | None:
        return get_period_end(subscription)


class OrganizationSummarySerializer(serializers.ModelSerializer):
    """The slice of an organization any member may see about their own org:
    enough for a client to label it and to route an unpaid org to billing
    before hitting a 402."""

    has_active_subscription = serializers.SerializerMethodField()
    payment_failed = serializers.SerializerMethodField()
    # When a deleted organization is purged for good; null unless deleted.
    deletion_scheduled_for = serializers.DateTimeField(
        source="purge_after", read_only=True, allow_null=True
    )

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "has_active_subscription",
            "payment_failed",
            "deletion_scheduled_for",
            "require_two_factor",
        ]
        read_only_fields = fields

    def get_has_active_subscription(self, organization) -> bool:
        return bool(organization.active_subscription)

    def get_payment_failed(self, organization) -> bool:
        """A renewal payment failed and Stripe is retrying it: the
        organization still has access, but its admins should update the
        payment details before Stripe gives up."""
        subscription = organization.active_subscription
        return bool(subscription) and is_past_due(subscription)


class OrganizationSerializer(serializers.ModelSerializer):
    """``billing_email`` uniqueness is checked here so a collision returns 400
    rather than surfacing as an IntegrityError."""

    # Null while the organization has no active subscription.
    active_subscription = ActiveSubscriptionSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "billing_email",
            "require_two_factor",
            "active_subscription",
            "created",
            "modified",
        ]
        read_only_fields = ["id", "created", "modified"]

    def validate_billing_email(self, value):
        return validate_unique_billing_email(value, organization=self.instance)

    def validate_require_two_factor(self, value):
        """An admin can't require what they haven't set up themselves: they'd
        be the first one held at the setup screen."""
        if value and not self.context["request"].user.two_factor_enabled:
            raise serializers.ValidationError(REQUIRE_TWO_FACTOR_WITHOUT_IT_MESSAGE)
        return value


class OrganizationSignupSerializer(serializers.Serializer):
    """Input for creating an Organization together with its first admin User."""

    name = serializers.CharField(max_length=100)
    billing_email = serializers.EmailField(required=False, allow_null=True)
    admin_email = serializers.EmailField()
    admin_password = serializers.CharField(write_only=True)
    # Optional: it can be added later from the account settings.
    admin_name = serializers.CharField(
        max_length=MAX_NAME_LENGTH, allow_blank=True, default=""
    )

    def validate_billing_email(self, value):
        return validate_unique_billing_email(value)

    def validate_admin_email(self, value):
        if User.objects.holding_email().filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        validate_password_for_field("admin_password", attrs["admin_password"])
        return attrs


class OrganizationDeletionSerializer(serializers.Serializer):
    """Deleting the organization is confirmed by typing its name."""

    name = serializers.CharField()

    def validate_name(self, value):
        if value.strip() != self.context["organization"].name:
            raise serializers.ValidationError(
                "Type the organization's name exactly as it's shown to confirm."
            )
        return value


class ExportDownloadSerializer(serializers.Serializer):
    """The token from the emailed download link."""

    token = serializers.CharField()
