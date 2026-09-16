from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from subscriptions.api.v1.serializers import (
    CheckoutSessionResponseSerializer,
    CheckoutSessionSerializer,
)
from subscriptions.mappings import PLAN_PRICE_IDS
from subscriptions.services import create_checkout_session
from users.permissions import IsOrganizationAdmin


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
                description="Invalid plan, or organization has no billing email set."
            ),
        },
    )
    def post(self, request):
        organization = request.user.organization
        serializer = CheckoutSessionSerializer(
            data=request.data, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)

        price_id = PLAN_PRICE_IDS[serializer.validated_data["plan"]]
        checkout_url = create_checkout_session(organization, price_id)

        return Response(
            CheckoutSessionResponseSerializer({"checkout_url": checkout_url}).data
        )
