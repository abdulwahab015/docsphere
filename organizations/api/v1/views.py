from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from audit.choices import AuditVerb
from audit.models import AuditEvent
from core.permissions import HasActiveSubscription
from organizations.api.v1.serializers import (
    ExportDownloadSerializer,
    OrganizationDeletionSerializer,
    OrganizationSerializer,
    OrganizationSignupSerializer,
)
from organizations.exports import (
    INVALID_EXPORT_LINK_MESSAGE,
    InvalidExportLinkError,
    read_export_token,
)
from organizations.models import Organization, OrganizationExport
from organizations.services import cancel_deletion, schedule_deletion
from organizations.tasks import build_organization_export_task
from organizations.throttles import OrganizationScopedRateThrottle
from subscriptions.services import sync_billing_email
from users.api.v1.serializers import TokenPairSerializer
from users.api.v1.tokens import token_pair_response
from users.choices import OrganizationRole
from users.permissions import (
    HasVerifiedEmail,
    IsOrganizationAdmin,
    MeetsTwoFactorRequirement,
)
from users.tasks import send_verification_email_task

User = get_user_model()

EXPORT_IN_PROGRESS_MESSAGE = (
    "An export of this organization is already being prepared. We'll email a link "
    "when it's ready."
)

_PROVIDER_ERROR = OpenApiResponse(
    description="Stripe couldn't be updated with the new billing email; nothing was saved."
)


class OrganizationSignupAPIView(APIView):
    """Creates an Organization together with its first admin User, atomically,
    and logs the admin in immediately with a JWT pair. The admin must follow
    the link emailed to them before they can do anything else."""

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
            User.objects.release_email(data["admin_email"])
            organization = Organization.objects.create(
                name=data["name"], billing_email=data.get("billing_email")
            )
            user = User.objects.create_user(
                email=data["admin_email"],
                password=data["admin_password"],
                name=data["admin_name"],
                organization=organization,
                org_role=OrganizationRole.ADMIN,
            )

        send_verification_email_task.delay(user.pk)

        return token_pair_response(user, status.HTTP_201_CREATED)


@extend_schema_view(
    put=extend_schema(responses={200: OrganizationSerializer, 502: _PROVIDER_ERROR}),
    patch=extend_schema(responses={200: OrganizationSerializer, 502: _PROVIDER_ERROR}),
)
class OrganizationProfileAPIView(generics.RetrieveUpdateAPIView):
    """Retrieve or update the requesting admin's own organization profile.
    Reachable without an active subscription, since fixing ``billing_email``
    is the prerequisite for checkout succeeding at all."""

    serializer_class = OrganizationSerializer
    permission_classes = [
        IsOrganizationAdmin,
        HasVerifiedEmail,
        MeetsTwoFactorRequirement,
    ]

    def get_object(self):
        return self.request.user.organization

    def perform_update(self, serializer):
        """A new billing email goes to the Stripe customer too, in the same
        transaction: if Stripe can't be updated, nothing is saved, so the
        receipts never go somewhere the app no longer shows."""
        previous_billing_email = serializer.instance.billing_email
        with transaction.atomic():
            organization = serializer.save()
            if organization.billing_email != previous_billing_email:
                sync_billing_email(organization)


class OrganizationDeleteAPIView(APIView):
    """An admin deletes their organization, confirming with its name: from
    then on nobody in it can use the app, the subscription is cancelled at
    once, and it's purged with everything in it after 30 days unless an
    admin restores it. Reachable without a subscription, so a lapsed
    organization can leave too."""

    permission_classes = [
        IsOrganizationAdmin,
        HasVerifiedEmail,
        MeetsTwoFactorRequirement,
    ]

    @extend_schema(
        request=OrganizationDeletionSerializer,
        responses={
            204: OpenApiResponse(description="Deleted; purged in 30 days."),
            400: OpenApiResponse(
                description="The name doesn't match, or it's already deleted."
            ),
            502: OpenApiResponse(
                description="Stripe couldn't cancel the subscription; nothing changed."
            ),
        },
    )
    def post(self, request):
        organization = request.user.organization
        if organization.deletion_requested_at:
            raise ValidationError({"detail": "This organization is already deleted."})
        serializer = OrganizationDeletionSerializer(
            data=request.data, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)

        schedule_deletion(organization)

        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationDeleteCancelAPIView(APIView):
    """An admin restores their deleted organization before it's purged. Its
    subscription stays cancelled."""

    permission_classes = [
        IsOrganizationAdmin,
        HasVerifiedEmail,
        MeetsTwoFactorRequirement,
    ]

    @extend_schema(
        request=None,
        responses={
            204: OpenApiResponse(description="Restored."),
            400: OpenApiResponse(description="The organization isn't deleted."),
        },
    )
    def post(self, request):
        organization = request.user.organization
        if not organization.deletion_requested_at:
            raise ValidationError({"detail": "This organization isn't deleted."})

        cancel_deletion(organization)

        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationExportCreateAPIView(APIView):
    """An admin asks for an export of the organization: it's built in the
    background and a download link is emailed to them. One at a time per
    organization, checked under a lock on it so two requests at once can't
    both start one, and a few a day (the ``organization_export`` rate, counted
    for the whole organization)."""

    permission_classes = [
        IsOrganizationAdmin,
        HasVerifiedEmail,
        MeetsTwoFactorRequirement,
        HasActiveSubscription,
    ]
    throttle_classes = [OrganizationScopedRateThrottle]
    throttle_scope = "organization_export"

    @extend_schema(
        request=None,
        responses={
            202: OpenApiResponse(description="Building; a link will be emailed."),
            400: OpenApiResponse(description="One is already being built."),
        },
    )
    def post(self, request):
        organization = request.user.organization
        with transaction.atomic():
            Organization.objects.select_for_update().get(pk=organization.pk)
            if OrganizationExport.objects.filter(organization=organization).building():
                raise ValidationError({"detail": EXPORT_IN_PROGRESS_MESSAGE})
            export = OrganizationExport.objects.create(
                organization=organization, requested_by=request.user
            )
            AuditEvent.objects.record(request.user, AuditVerb.EXPORT_REQUESTED)
        transaction.on_commit(lambda: build_organization_export_task.delay(export.pk))

        return Response(status=status.HTTP_202_ACCEPTED)


class OrganizationExportDownloadAPIView(APIView):
    """Downloads an export from the token in its emailed link, for an admin
    of its organization, while the link hasn't expired."""

    permission_classes = [
        IsOrganizationAdmin,
        HasVerifiedEmail,
        MeetsTwoFactorRequirement,
        HasActiveSubscription,
    ]

    @extend_schema(
        parameters=[OpenApiParameter("token", str, required=True)],
        responses={
            (200, "application/zip"): OpenApiTypes.BINARY,
            400: OpenApiResponse(description="Invalid or expired link."),
        },
    )
    def get(self, request):
        serializer = ExportDownloadSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            export_id = read_export_token(serializer.validated_data["token"])
        except InvalidExportLinkError:
            raise ValidationError({"detail": INVALID_EXPORT_LINK_MESSAGE}) from None
        export = get_object_or_404(
            OrganizationExport.objects.filter(
                organization=request.user.organization
            ).ready(),
            pk=export_id,
        )
        AuditEvent.objects.record(request.user, AuditVerb.EXPORT_DOWNLOADED)

        response = FileResponse(
            export.file.open("rb"),
            as_attachment=True,
            filename=f"docsphere-export-{export.created:%Y-%m-%d}.zip",
            content_type="application/zip",
        )
        response["Cache-Control"] = "private, no-store"
        return response
