from django.urls import path

from audit.api.v1.views import AuditEventListAPIView

urlpatterns = [
    path("events/", AuditEventListAPIView.as_view(), name="audit_event_list"),
]
