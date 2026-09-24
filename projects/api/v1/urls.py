from django.urls import path

from projects.api.v1.views import (
    DocumentAccessRequestApproveAPIView,
    DocumentAccessRequestDenyAPIView,
    DocumentAccessRequestListCreateAPIView,
    DocumentListCreateAPIView,
    DocumentRestoreAPIView,
    DocumentRetrieveUpdateDestroyAPIView,
    DocumentShareAPIView,
    DocumentShareRevokeAPIView,
    DocumentTrashListAPIView,
    IncomingDocumentAccessRequestListAPIView,
    MyDocumentAccessRequestListAPIView,
    ProjectListCreateAPIView,
    ProjectRestoreAPIView,
    ProjectRetrieveUpdateDestroyAPIView,
    ProjectShareAPIView,
    ProjectShareRevokeAPIView,
    ProjectTrashListAPIView,
)

urlpatterns = [
    path("", ProjectListCreateAPIView.as_view(), name="project_list_create"),
    path("trash/", ProjectTrashListAPIView.as_view(), name="project_trash"),
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
    path("trash/", DocumentTrashListAPIView.as_view(), name="document_trash"),
    path(
        "access-requests/mine/",
        MyDocumentAccessRequestListAPIView.as_view(),
        name="document_access_request_mine",
    ),
    path(
        "access-requests/incoming/",
        IncomingDocumentAccessRequestListAPIView.as_view(),
        name="document_access_request_incoming",
    ),
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
    path(
        "<int:pk>/access-requests/",
        DocumentAccessRequestListCreateAPIView.as_view(),
        name="document_access_request_list_create",
    ),
    path(
        "<int:pk>/access-requests/<int:request_id>/approve/",
        DocumentAccessRequestApproveAPIView.as_view(),
        name="document_access_request_approve",
    ),
    path(
        "<int:pk>/access-requests/<int:request_id>/deny/",
        DocumentAccessRequestDenyAPIView.as_view(),
        name="document_access_request_deny",
    ),
]
