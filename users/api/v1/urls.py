from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from users.api.v1.views import (
    DeactivateUserAPIView,
    InvitationAcceptAPIView,
    InvitationBulkCreateAPIView,
    InvitationListCreateAPIView,
    LoginView,
    LogoutAPIView,
    PasswordResetConfirmAPIView,
    PasswordResetRequestAPIView,
)

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth_login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth_refresh"),
    path("auth/logout/", LogoutAPIView.as_view(), name="auth_logout"),
    path(
        "auth/password-reset/",
        PasswordResetRequestAPIView.as_view(),
        name="auth_password_reset",
    ),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmAPIView.as_view(),
        name="auth_password_reset_confirm",
    ),
    path(
        "invitations/",
        InvitationListCreateAPIView.as_view(),
        name="invitation_list_create",
    ),
    path(
        "invitations/bulk/",
        InvitationBulkCreateAPIView.as_view(),
        name="invitation_bulk_create",
    ),
    path(
        "invitations/accept/",
        InvitationAcceptAPIView.as_view(),
        name="invitation_accept",
    ),
    path(
        "<int:pk>/deactivate/",
        DeactivateUserAPIView.as_view(),
        name="user_deactivate",
    ),
]
