from django.urls import path

from organizations.api.v1.views import (
    OrganizationDeleteAPIView,
    OrganizationDeleteCancelAPIView,
    OrganizationExportCreateAPIView,
    OrganizationExportDownloadAPIView,
    OrganizationProfileAPIView,
    OrganizationSignupAPIView,
)

urlpatterns = [
    path("signup/", OrganizationSignupAPIView.as_view(), name="organization_signup"),
    path("profile/", OrganizationProfileAPIView.as_view(), name="organization_profile"),
    path("delete/", OrganizationDeleteAPIView.as_view(), name="organization_delete"),
    path(
        "delete/cancel/",
        OrganizationDeleteCancelAPIView.as_view(),
        name="organization_delete_cancel",
    ),
    path(
        "exports/",
        OrganizationExportCreateAPIView.as_view(),
        name="organization_export_create",
    ),
    path(
        "exports/download/",
        OrganizationExportDownloadAPIView.as_view(),
        name="organization_export_download",
    ),
]
