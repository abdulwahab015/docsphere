from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from users.views import (
    DeactivateUserView,
    InvitationAcceptView,
    InvitationBulkCreateView,
    InvitationListCreateView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
)

urlpatterns = [
    path("auth/login/", TokenObtainPairView.as_view(), name="auth_login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth_logout"),
    path(
        "auth/password-reset/",
        PasswordResetRequestView.as_view(),
        name="auth_password_reset",
    ),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth_password_reset_confirm",
    ),
    path(
        "invitations/",
        InvitationListCreateView.as_view(),
        name="invitation_list_create",
    ),
    path(
        "invitations/bulk/",
        InvitationBulkCreateView.as_view(),
        name="invitation_bulk_create",
    ),
    path(
        "invitations/accept/", InvitationAcceptView.as_view(), name="invitation_accept"
    ),
    path(
        "<int:pk>/deactivate/",
        DeactivateUserView.as_view(),
        name="user_deactivate",
    ),
]
