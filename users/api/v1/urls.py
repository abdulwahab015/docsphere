from django.urls import path

from users.api.v1.views import (
    CookieTokenRefreshView,
    CurrentUserAPIView,
    DeactivatedUserListAPIView,
    DeactivateUserAPIView,
    InvitationAcceptAPIView,
    InvitationBulkCreateAPIView,
    InvitationListCreateAPIView,
    InvitationResendAPIView,
    InvitationRevokeAPIView,
    LoginView,
    LogoutAPIView,
    OrganizationRoleUpdateAPIView,
    PasswordChangeAPIView,
    PasswordResetConfirmAPIView,
    PasswordResetRequestAPIView,
    ReactivateUserAPIView,
    UserListAPIView,
)

urlpatterns = [
    path("", UserListAPIView.as_view(), name="user_list"),
    path("me/", CurrentUserAPIView.as_view(), name="user_me"),
    path("me/password/", PasswordChangeAPIView.as_view(), name="user_password_change"),
    path(
        "deactivated/",
        DeactivatedUserListAPIView.as_view(),
        name="user_deactivated_list",
    ),
    path("auth/login/", LoginView.as_view(), name="auth_login"),
    path("auth/refresh/", CookieTokenRefreshView.as_view(), name="auth_refresh"),
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
        "invitations/<int:pk>/",
        InvitationRevokeAPIView.as_view(),
        name="invitation_revoke",
    ),
    path(
        "invitations/<int:pk>/resend/",
        InvitationResendAPIView.as_view(),
        name="invitation_resend",
    ),
    path(
        "<int:pk>/deactivate/",
        DeactivateUserAPIView.as_view(),
        name="user_deactivate",
    ),
    path(
        "<int:pk>/reactivate/",
        ReactivateUserAPIView.as_view(),
        name="user_reactivate",
    ),
    path(
        "<int:pk>/role/",
        OrganizationRoleUpdateAPIView.as_view(),
        name="user_role_update",
    ),
]
