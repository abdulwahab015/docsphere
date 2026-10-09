from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.email import email_task, send_templated_mail
from users.email_links import make_email_change_token, make_verification_token
from users.models import Invitation

User = get_user_model()


@email_task
def send_invitation_email_task(invitation_id):
    invitation = Invitation.objects.select_related("organization").get(pk=invitation_id)

    send_templated_mail(
        "users/email/invitation",
        {
            "organization_name": invitation.organization.name,
            "accept_url": (
                f"{settings.FRONTEND_URL}/accept-invite?token={invitation.token}"
            ),
        },
        [invitation.email],
    )


@email_task
def send_password_reset_email_task(user_id):
    user = User.objects.get(pk=user_id)

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    send_templated_mail(
        "users/email/password_reset",
        {
            "reset_url": (
                f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
            ),
        },
        [user.email],
    )


@email_task
def send_verification_email_task(user_id):
    user = User.objects.select_related("organization").get(pk=user_id)

    send_templated_mail(
        "users/email/email_verification",
        {
            "organization_name": user.organization.name,
            "verify_url": (
                f"{settings.FRONTEND_URL}/verify-email"
                f"?token={make_verification_token(user)}"
            ),
        },
        [user.email],
    )


@email_task
def send_email_change_link_task(user_id, new_email):
    """Sent to the new address: following the link proves it's theirs."""
    user = User.objects.get(pk=user_id)

    send_templated_mail(
        "users/email/email_change",
        {
            "current_email": user.email,
            "confirm_url": (
                f"{settings.FRONTEND_URL}/confirm-email"
                f"?token={make_email_change_token(user, new_email)}"
            ),
        },
        [new_email],
    )


@email_task
def send_email_changed_notice_task(old_email, new_email):
    """Sent to the address an account just moved away from, so its owner
    finds out if someone else made the change."""
    send_templated_mail(
        "users/email/email_changed",
        {"old_email": old_email, "new_email": new_email},
        [old_email],
    )


@email_task
def send_two_factor_reset_email_task(user_id, admin_id):
    """Sent when an admin turns off someone's two-factor sign-in, so they
    find out if they didn't ask for it."""
    user = User.objects.get(pk=user_id)
    admin = User.objects.get(pk=admin_id)

    send_templated_mail(
        "users/email/two_factor_reset",
        {
            "admin_name": admin.name_and_email,
            "email": user.email,
            "account_url": f"{settings.FRONTEND_URL}/settings/account",
        },
        [user.email],
    )


@shared_task
def remove_unverified_accounts_task():
    """Daily: deletes signups that never verified their address in time,
    with their organizations, so the addresses are free again."""
    User.objects.unverified_past_expiry().delete_with_organizations()
