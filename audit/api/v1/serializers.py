from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from audit.choices import AuditKind
from audit.mappings import RESOURCE_CONTENT_DETAILS
from audit.models import AuditEvent
from projects.choices import AccessLevel, ResourceKind, Visibility
from users.choices import OrganizationRole


class AuditEventDetailsSerializer(serializers.Serializer):
    """What changed; each verb carries only the details that apply to it."""

    access_level = serializers.ChoiceField(choices=AccessLevel.choices, required=False)
    previous_access_level = serializers.ChoiceField(
        choices=AccessLevel.choices, required=False
    )
    visibility = serializers.ChoiceField(choices=Visibility.choices, required=False)
    role = serializers.ChoiceField(choices=OrganizationRole.choices, required=False)
    previous_role = serializers.ChoiceField(
        choices=OrganizationRole.choices, required=False
    )
    email = serializers.EmailField(required=False)
    file_name = serializers.CharField(required=False)
    size = serializers.IntegerField(required=False)


class AuditEventSerializer(serializers.ModelSerializer):
    """One event as an admin sees it. A project or document they couldn't
    open goes unnamed - its name and any detail of what's in it (a file name)
    are left out - but the event itself is still listed. Needs a queryset
    annotated by ``with_resource_access``."""

    actor_email = serializers.EmailField(
        source="actor.email", read_only=True, allow_null=True
    )
    actor_name = serializers.CharField(
        source="actor.name", read_only=True, allow_null=True
    )
    target_user_email = serializers.EmailField(
        source="target_user.email", read_only=True, allow_null=True
    )
    target_user_name = serializers.CharField(
        source="target_user.name", read_only=True, allow_null=True
    )
    resource_kind = serializers.SerializerMethodField()
    resource_name = serializers.SerializerMethodField()
    details = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "created",
            "verb",
            "actor_email",
            "actor_name",
            "target_user_email",
            "target_user_name",
            "resource_kind",
            "resource_name",
            "details",
        ]
        read_only_fields = fields

    @extend_schema_field(
        serializers.ChoiceField(choices=ResourceKind.choices, allow_null=True)
    )
    def get_resource_kind(self, event):
        if event.project_id:
            return ResourceKind.PROJECT
        if event.document_id:
            return ResourceKind.DOCUMENT
        return None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_resource_name(self, event):
        if not event.resource_visible:
            return None
        if event.project:
            return event.project.name
        if event.document:
            return event.document.title
        return None

    @extend_schema_field(AuditEventDetailsSerializer)
    def get_details(self, event):
        details = event.details
        if not event.resource_visible:
            details = {
                key: value
                for key, value in details.items()
                if key not in RESOURCE_CONTENT_DETAILS
            }
        return AuditEventDetailsSerializer(details).data


class AuditEventFilterSerializer(serializers.Serializer):
    """The activity list's optional filters, from the query string."""

    kind = serializers.ChoiceField(choices=AuditKind.choices, required=False)
    after = serializers.DateTimeField(required=False)
    before = serializers.DateTimeField(required=False)
