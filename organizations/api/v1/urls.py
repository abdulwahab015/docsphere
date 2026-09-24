from django.urls import path

from organizations.api.v1.views import (
    OrganizationProfileAPIView,
    OrganizationSignupAPIView,
)

urlpatterns = [
    path("signup/", OrganizationSignupAPIView.as_view(), name="organization_signup"),
    path("profile/", OrganizationProfileAPIView.as_view(), name="organization_profile"),
]
