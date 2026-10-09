from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.api.v1.serializers import (
    NotificationSerializer,
    UnreadCountSerializer,
)
from notifications.models import Notification


class NotificationListAPIView(generics.ListAPIView):
    """The caller's own notifications, newest first."""

    serializer_class = NotificationSerializer

    def get_queryset(self):
        user = self.request.user
        return (
            Notification.objects.for_recipient(user)
            .with_resource_access(user)
            .select_related("actor", "project", "document")
            .order_by("-created", "-pk")
        )


class UnreadNotificationCountAPIView(APIView):
    """How many of the caller's notifications are unread - what the app
    polls for its badge."""

    @extend_schema(responses=UnreadCountSerializer)
    def get(self, request):
        count = Notification.objects.for_recipient(request.user).unread().count()
        return Response(UnreadCountSerializer({"count": count}).data)


class NotificationReadAPIView(APIView):
    """Marks one of the caller's notifications read; anyone else's is a
    404. Reading it again changes nothing."""

    @extend_schema(request=None, responses={204: None})
    def post(self, request, pk):
        notification = get_object_or_404(
            Notification.objects.for_recipient(request.user), pk=pk
        )
        Notification.objects.filter(pk=notification.pk).mark_read()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationReadAllAPIView(APIView):
    """Marks every one of the caller's notifications read."""

    @extend_schema(
        request=None,
        responses={204: OpenApiResponse(description="All marked read.")},
    )
    def post(self, request):
        Notification.objects.for_recipient(request.user).mark_read()
        return Response(status=status.HTTP_204_NO_CONTENT)
