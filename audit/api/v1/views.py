from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.filters import SearchFilter

from audit.api.v1.serializers import AuditEventFilterSerializer, AuditEventSerializer
from audit.choices import AuditKind
from audit.models import AuditEvent
from core.permissions import HasActiveSubscription
from users.permissions import HasVerifiedEmail, IsOrganizationAdmin


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(
                "kind", str, enum=AuditKind.values, description="Only this kind."
            ),
            OpenApiParameter(
                "after",
                str,
                description="Only events at or after this time (ISO 8601).",
            ),
            OpenApiParameter(
                "before", str, description="Only events before this time (ISO 8601)."
            ),
        ]
    )
)
class AuditEventListAPIView(generics.ListAPIView):
    """The organization's activity, newest first - admins only.
    ``?search=`` matches the name or email of who did it, who it was about,
    or the address an invitation went to."""

    serializer_class = AuditEventSerializer
    permission_classes = [IsOrganizationAdmin, HasVerifiedEmail, HasActiveSubscription]
    filter_backends = [SearchFilter]
    search_fields = [
        "actor__email",
        "actor__name",
        "target_user__email",
        "target_user__name",
        "details__email",
    ]

    def get_queryset(self):
        filters = AuditEventFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        kind = filters.validated_data.get("kind")
        after = filters.validated_data.get("after")
        before = filters.validated_data.get("before")

        events = AuditEvent.objects.for_organization(self.request.user.organization)
        if kind:
            events = events.of_kind(kind)
        if after:
            events = events.filter(created__gte=after)
        if before:
            events = events.filter(created__lt=before)
        return (
            events.with_resource_access(self.request.user)
            .select_related("actor", "target_user", "project", "document")
            .order_by("-created", "-pk")
        )
