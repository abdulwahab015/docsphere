from djstripe.models import Price
from rest_framework import serializers

from subscriptions.utils import active_recurring_prices

ORGANIZATION_DELETED_MESSAGE = (
    "Your organization has been deleted. Restore it before subscribing again."
)
ALREADY_SUBSCRIBED_MESSAGE = (
    "Your organization already has an active subscription. "
    "Manage it from the billing portal."
)


class PriceSerializer(serializers.ModelSerializer):
    """A subscribable plan, as a client needs it to render a plan picker and
    pass ``id`` on to checkout. ``unit_amount`` is in the currency's smallest
    unit (e.g. cents)."""

    product_name = serializers.CharField(source="product.name", read_only=True)
    unit_amount = serializers.SerializerMethodField()
    interval = serializers.SerializerMethodField()

    class Meta:
        model = Price
        fields = [
            "id",
            "nickname",
            "product_name",
            "unit_amount",
            "currency",
            "interval",
        ]
        read_only_fields = fields

    def get_unit_amount(self, price) -> int | None:
        return price.stripe_data.get("unit_amount")

    def get_interval(self, price) -> str | None:
        return (price.stripe_data.get("recurring") or {}).get("interval")


class CheckoutSessionSerializer(serializers.Serializer):
    price_id = serializers.CharField()

    def validate_price_id(self, value):
        is_active_recurring_price = active_recurring_prices().filter(id=value).exists()
        if not is_active_recurring_price:
            raise serializers.ValidationError("No such active recurring price.")
        return value

    def validate(self, attrs):
        organization = self.context["organization"]
        if organization.deletion_requested_at:
            raise serializers.ValidationError(ORGANIZATION_DELETED_MESSAGE)
        if not organization.billing_email:
            raise serializers.ValidationError("Organization billing email is not set.")
        # A second checkout would start a second, separately billed subscription.
        if organization.active_subscription:
            raise serializers.ValidationError(ALREADY_SUBSCRIBED_MESSAGE)
        return attrs


class CheckoutSessionResponseSerializer(serializers.Serializer):
    checkout_url = serializers.URLField()


class BillingPortalSessionResponseSerializer(serializers.Serializer):
    portal_url = serializers.URLField()
