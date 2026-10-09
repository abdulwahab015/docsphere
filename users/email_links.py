"""Signed, expiring tokens for the emailed links that prove someone owns an
address: verifying a new signup's email, and confirming a change to a new one.

Nothing is stored. Each token is signed with the secret key and names the
account and the address it was sent for, so it stops working after
``EMAIL_LINK_EXPIRY`` or as soon as the account's email changes - a used
change-email link, or any older one, can't be used again.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing

User = get_user_model()

INVALID_EMAIL_LINK_MESSAGE = "This link is invalid or has expired."

_VERIFICATION_SALT = "users.email-verification"
_EMAIL_CHANGE_SALT = "users.email-change"


class InvalidEmailLinkError(Exception):
    """Forged, expired, or for an address the account no longer has."""


def make_verification_token(user):
    return signing.dumps(
        {"user": user.pk, "email": user.email}, salt=_VERIFICATION_SALT
    )


def make_email_change_token(user, new_email):
    return signing.dumps(
        {"user": user.pk, "email": user.email, "new_email": new_email},
        salt=_EMAIL_CHANGE_SALT,
    )


def read_verification_token(token):
    """The account whose address the link was sent to."""
    user, _ = _read(token, _VERIFICATION_SALT)
    return user


def read_email_change_token(token):
    """The account, and the new address it asked to move to."""
    user, payload = _read(token, _EMAIL_CHANGE_SALT)
    return user, payload["new_email"]


def _read(token, salt):
    try:
        payload = signing.loads(
            token, salt=salt, max_age=settings.EMAIL_LINK_EXPIRY.total_seconds()
        )
    except signing.BadSignature:  # SignatureExpired is a BadSignature too.
        raise InvalidEmailLinkError from None

    user = User.objects.filter(
        pk=payload["user"], email=payload["email"], is_active=True
    ).first()
    if not user:
        raise InvalidEmailLinkError
    return user, payload
