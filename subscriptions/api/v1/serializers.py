from djstripe.models import Price
from rest_framework import serializers


class CheckoutSessionSerializer(serializers.Serializer):
    price_id = serializers.CharField()

    def validate_price_id(self, value):
        is_active_recurring_price = Price.objects.filter(
            id=value, active=True, stripe_data__type="recurring"
        ).exists()
        if not is_active_recurring_price:
            raise serializers.ValidationError("No such active recurring price.")
        return value

    def validate(self, attrs):
        organization = self.context["organization"]
        if not organization.billing_email:
            raise serializers.ValidationError("Organization billing email is not set.")
        return attrs


class CheckoutSessionResponseSerializer(serializers.Serializer):
    checkout_url = serializers.URLField()
