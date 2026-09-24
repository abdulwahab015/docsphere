from django.contrib.auth import get_user_model
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from organizations.api.v1.serializers import (
    OrganizationSerializer,
    OrganizationSignupSerializer,
)
from organizations.models import Organization
from users.api.v1.serializers import TokenPairSerializer
from users.api.v1.tokens import token_pair_response
from users.choices import OrganizationRole
from users.permissions import IsOrganizationAdmin

User = get_user_model()


class OrganizationSignupAPIView(APIView):
    """Creates an Organization together with its first admin User, atomically,
    and logs the admin in immediately with a JWT pair."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "org_signup"

    @extend_schema(
        request=OrganizationSignupSerializer,
        responses={201: TokenPairSerializer},
    )
    def post(self, request):
        serializer = OrganizationSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            organization = Organization.objects.create(
                name=data["name"], billing_email=data.get("billing_email")
            )
            user = User.objects.create_user(
                email=data["admin_email"],
                password=data["admin_password"],
                organization=organization,
                org_role=OrganizationRole.ADMIN,
            )

        return token_pair_response(user, status.HTTP_201_CREATED)


class OrganizationProfileAPIView(generics.RetrieveUpdateAPIView):
    """Retrieve or update the requesting admin's own organization profile.
    Reachable without an active subscription, since fixing ``billing_email``
    is the prerequisite for checkout succeeding at all."""

    serializer_class = OrganizationSerializer
    permission_classes = [IsOrganizationAdmin]

    def get_object(self):
        return self.request.user.organization
