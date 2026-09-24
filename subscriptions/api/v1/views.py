from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from subscriptions.api.v1.serializers import (
    BillingPortalSessionResponseSerializer,
    CheckoutSessionResponseSerializer,
    CheckoutSessionSerializer,
    PriceSerializer,
)
from subscriptions.services import (
    create_billing_portal_session,
    create_checkout_session,
)
from subscriptions.utils import active_recurring_prices
from users.permissions import IsOrganizationAdmin


class PriceListAPIView(generics.ListAPIView):
    """Lists the plans an admin can pick from before starting checkout,
    cheapest first. Like checkout itself, reachable without an active
    subscription."""

    serializer_class = PriceSerializer
    permission_classes = [IsOrganizationAdmin]

    def get_queryset(self):
        return (
            active_recurring_prices()
            .select_related("product")
            .order_by("stripe_data__unit_amount", "id")
        )


class CheckoutSessionCreateAPIView(APIView):
    """Creates a Stripe Checkout Session for the requesting admin's
    organization and returns its URL for the frontend to redirect to.

    Deliberately excludes ``HasActiveSubscription`` — an organization
    starting checkout has no subscription yet, that's the point.
    """

    permission_classes = [IsOrganizationAdmin]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "billing_checkout"

    @extend_schema(
        request=CheckoutSessionSerializer,
        responses={
            200: CheckoutSessionResponseSerializer,
            400: OpenApiResponse(
                description="Invalid price, or organization has no billing email set."
            ),
        },
    )
    def post(self, request):
        organization = request.user.organization
        serializer = CheckoutSessionSerializer(
            data=request.data, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)

        price_id = serializer.validated_data["price_id"]
        checkout_url = create_checkout_session(organization, price_id)

        return Response(
            CheckoutSessionResponseSerializer({"checkout_url": checkout_url}).data
        )


class BillingPortalSessionCreateAPIView(APIView):
    """Creates a Stripe Customer Portal session for the requesting admin's
    organization - where they update payment details or cancel - and returns
    its URL for the frontend to redirect to. Reachable without an active
    subscription, so a lapsed organization can fix its payment method."""

    permission_classes = [IsOrganizationAdmin]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "billing_portal"

    @extend_schema(
        request=None,
        responses={
            200: BillingPortalSessionResponseSerializer,
            400: OpenApiResponse(
                description="Organization has never subscribed, so has no billing account."
            ),
        },
    )
    def post(self, request):
        portal_url = create_billing_portal_session(request.user.organization)
        if not portal_url:
            raise ValidationError(
                {
                    "detail": "Your organization has no billing account yet; subscribe first."
                }
            )

        return Response(
            BillingPortalSessionResponseSerializer({"portal_url": portal_url}).data
        )
