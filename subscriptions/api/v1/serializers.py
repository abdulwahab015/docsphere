from rest_framework import serializers

from clients import stripe as stripe_client


class CheckoutSessionSerializer(serializers.Serializer):
    price_id = serializers.CharField()

    def validate_price_id(self, value):
        if not stripe_client.is_active_recurring_price(value):
            raise serializers.ValidationError("No such active recurring price.")
        return value

    def validate(self, attrs):
        organization = self.context["organization"]
        if not organization.billing_email:
            raise serializers.ValidationError("Organization billing email is not set.")
        return attrs


class CheckoutSessionResponseSerializer(serializers.Serializer):
    checkout_url = serializers.URLField()
