from rest_framework import serializers

from subscriptions.choices import Plan


class CheckoutSessionSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=Plan.choices)

    def validate(self, attrs):
        organization = self.context["organization"]
        if not organization.billing_email:
            raise serializers.ValidationError("Organization billing email is not set.")
        return attrs


class CheckoutSessionResponseSerializer(serializers.Serializer):
    checkout_url = serializers.URLField()
