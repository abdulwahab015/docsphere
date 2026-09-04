from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.email import send_templated_mail
from users.models import Invitation

User = get_user_model()


@shared_task
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


@shared_task
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
