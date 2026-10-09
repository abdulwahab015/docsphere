from django.urls import path

from notifications.api.v1.views import (
    NotificationListAPIView,
    NotificationReadAllAPIView,
    NotificationReadAPIView,
    UnreadNotificationCountAPIView,
)

urlpatterns = [
    path("", NotificationListAPIView.as_view(), name="notification_list"),
    path(
        "unread-count/",
        UnreadNotificationCountAPIView.as_view(),
        name="notification_unread_count",
    ),
    path(
        "read-all/", NotificationReadAllAPIView.as_view(), name="notification_read_all"
    ),
    path("<int:pk>/read/", NotificationReadAPIView.as_view(), name="notification_read"),
]
