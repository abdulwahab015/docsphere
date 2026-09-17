from django.urls import path

from projects.api.v1.views import (
    ProjectListCreateAPIView,
    ProjectRestoreAPIView,
    ProjectRetrieveUpdateDestroyAPIView,
)

urlpatterns = [
    path("", ProjectListCreateAPIView.as_view(), name="project_list_create"),
    path(
        "<int:pk>/",
        ProjectRetrieveUpdateDestroyAPIView.as_view(),
        name="project_detail",
    ),
    path("<int:pk>/restore/", ProjectRestoreAPIView.as_view(), name="project_restore"),
]
