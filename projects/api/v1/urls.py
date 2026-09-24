from django.urls import path

from projects.api.v1.views import (
    DocumentListCreateAPIView,
    DocumentRestoreAPIView,
    DocumentRetrieveUpdateDestroyAPIView,
    DocumentShareAPIView,
    DocumentShareRevokeAPIView,
    ProjectListCreateAPIView,
    ProjectRestoreAPIView,
    ProjectRetrieveUpdateDestroyAPIView,
    ProjectShareAPIView,
    ProjectShareRevokeAPIView,
)

urlpatterns = [
    path("", ProjectListCreateAPIView.as_view(), name="project_list_create"),
    path(
        "<int:pk>/",
        ProjectRetrieveUpdateDestroyAPIView.as_view(),
        name="project_detail",
    ),
    path("<int:pk>/restore/", ProjectRestoreAPIView.as_view(), name="project_restore"),
    path("<int:pk>/share/", ProjectShareAPIView.as_view(), name="project_share"),
    path(
        "<int:pk>/share/<int:user_id>/",
        ProjectShareRevokeAPIView.as_view(),
        name="project_share_revoke",
    ),
]

document_urlpatterns = [
    path("", DocumentListCreateAPIView.as_view(), name="document_list_create"),
    path(
        "<int:pk>/",
        DocumentRetrieveUpdateDestroyAPIView.as_view(),
        name="document_detail",
    ),
    path(
        "<int:pk>/restore/",
        DocumentRestoreAPIView.as_view(),
        name="document_restore",
    ),
    path("<int:pk>/share/", DocumentShareAPIView.as_view(), name="document_share"),
    path(
        "<int:pk>/share/<int:user_id>/",
        DocumentShareRevokeAPIView.as_view(),
        name="document_share_revoke",
    ),
]
