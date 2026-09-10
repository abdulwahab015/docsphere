from django.urls import path

from projects.api.v1.views import ProjectDetailAPIView, ProjectListCreateAPIView

urlpatterns = [
    path("", ProjectListCreateAPIView.as_view(), name="project_list_create"),
    path("<int:pk>/", ProjectDetailAPIView.as_view(), name="project_detail"),
]
