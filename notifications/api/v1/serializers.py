from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from notifications.models import Notification
from projects.choices import AccessLevel, ResourceKind


class NotificationDetailsSerializer(serializers.Serializer):
    access_level = serializers.ChoiceField(choices=AccessLevel.choices, required=False)


class NotificationSerializer(serializers.ModelSerializer):
    """One notification for its recipient. A project or document they can no
    longer open (access taken away, or made private) is left unnamed and
    unlinked. Needs a queryset annotated by ``with_resource_access``."""

    actor_email = serializers.EmailField(
        source="actor.email", read_only=True, allow_null=True
    )
    actor_name = serializers.CharField(
        source="actor.name", read_only=True, allow_null=True
    )
    read = serializers.SerializerMethodField()
    resource_kind = serializers.SerializerMethodField()
    resource_id = serializers.SerializerMethodField()
    resource_name = serializers.SerializerMethodField()
    details = NotificationDetailsSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "created",
            "verb",
            "read",
            "actor_email",
            "actor_name",
            "resource_kind",
            "resource_id",
            "resource_name",
            "details",
        ]
        read_only_fields = fields

    def get_read(self, notification) -> bool:
        return bool(notification.read_at)

    @extend_schema_field(
        serializers.ChoiceField(choices=ResourceKind.choices, allow_null=True)
    )
    def get_resource_kind(self, notification):
        if notification.project_id:
            return ResourceKind.PROJECT
        if notification.document_id:
            return ResourceKind.DOCUMENT
        return None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_resource_id(self, notification):
        if not notification.resource_visible:
            return None
        return notification.project_id or notification.document_id

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_resource_name(self, notification):
        if not notification.resource_visible:
            return None
        if notification.project:
            return notification.project.name
        if notification.document:
            return notification.document.title
        return None


class UnreadCountSerializer(serializers.Serializer):
    count = serializers.IntegerField()
