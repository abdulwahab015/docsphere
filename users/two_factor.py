"""Two-factor sign-in: codes from an authenticator app (TOTP, RFC 6238), the
one-time recovery codes that stand in for them, and the signed token that
carries a sign-in from the password step to the code step.

Each code works once: an accepted code's time step is stored, and only a
later step is accepted after it, claimed by a conditional update so two
requests with the same code can't both pass. A recovery code is used up the
same way.
"""

import hashlib
import hmac
import secrets

import pyotp
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from users.constants import (
    RECOVERY_CODE_ALPHABET,
    RECOVERY_CODE_COUNT,
    RECOVERY_CODE_LENGTH,
    TOTP_CODE_DIGITS,
    TOTP_VALID_WINDOW,
    TWO_FACTOR_ISSUER,
    TWO_FACTOR_LOGIN_TIMEOUT,
)
from users.models import RecoveryCode

User = get_user_model()

INVALID_CODE_MESSAGE = (
    "That code didn't work. Enter the current code from your authenticator "
    "app, or one of your recovery codes."
)
EXPIRED_SIGN_IN_MESSAGE = "Your sign-in has expired. Log in again."

_LOGIN_SALT = "users.two-factor-login"


class InvalidTwoFactorLoginError(Exception):
    """Forged or expired, or the account can no longer sign in this way."""


def start_setup(user):
    """Gives ``user`` a new authenticator key, not yet on: a code from the
    app confirms it. Starting again replaces a key that was never confirmed."""
    user.totp_secret = pyotp.random_base32()
    user.totp_last_used_step = None
    user.save(update_fields=["totp_secret", "totp_last_used_step"])


def provisioning_uri(user):
    """The ``otpauth://`` address an authenticator app reads from the QR
    code."""
    return pyotp.TOTP(user.totp_secret, digits=TOTP_CODE_DIGITS).provisioning_uri(
        name=user.email, issuer_name=TWO_FACTOR_ISSUER
    )


def _matching_step(user, code):
    """The time step, near now and after the last one used, whose code is
    ``code`` - or ``None``."""
    totp = pyotp.TOTP(user.totp_secret, digits=TOTP_CODE_DIGITS)
    current = totp.timecode(timezone.now())
    for step in range(current - TOTP_VALID_WINDOW, current + TOTP_VALID_WINDOW + 1):
        is_new = not user.totp_last_used_step or step > user.totp_last_used_step
        if is_new and hmac.compare_digest(totp.generate_otp(step), code):
            return step
    return None


def verify_app_code(user, code):
    """Whether ``code`` is a current code from ``user``'s authenticator app
    that hasn't been used yet. Using it marks it used."""
    if not user.totp_secret:
        return False
    step = _matching_step(user, code)
    if not step:
        return False

    claimed = (
        User.objects.filter(pk=user.pk)
        .filter(Q(totp_last_used_step__isnull=True) | Q(totp_last_used_step__lt=step))
        .update(totp_last_used_step=step)
    )
    if not claimed:
        return False
    user.totp_last_used_step = step
    return True


def _normalize_recovery_code(code):
    return "".join(code.lower().split()).replace("-", "")


def _hash_recovery_code(code):
    return hashlib.sha256(code.encode()).hexdigest()


def _format_recovery_code(code):
    half = RECOVERY_CODE_LENGTH // 2
    return f"{code[:half]}-{code[half:]}"


def issue_recovery_codes(user):
    """Replaces ``user``'s recovery codes with a new set and returns them -
    the only time they're ever shown."""
    codes = [
        "".join(
            secrets.choice(RECOVERY_CODE_ALPHABET) for _ in range(RECOVERY_CODE_LENGTH)
        )
        for _ in range(RECOVERY_CODE_COUNT)
    ]
    with transaction.atomic():
        RecoveryCode.objects.filter(user=user).delete()
        RecoveryCode.objects.bulk_create(
            RecoveryCode(user=user, code_hash=_hash_recovery_code(code))
            for code in codes
        )
    return [_format_recovery_code(code) for code in codes]


def use_recovery_code(user, code):
    """Whether ``code`` is one of ``user``'s unused recovery codes, which it
    then uses up. Dashes, spaces and case don't matter."""
    used = (
        RecoveryCode.objects.unused()
        .filter(
            user=user, code_hash=_hash_recovery_code(_normalize_recovery_code(code))
        )
        .update(used_at=timezone.now())
    )
    return bool(used)


def verify_second_factor(user, code):
    """A code from the authenticator app or, if it isn't one, a recovery
    code."""
    code = code.strip()
    if code.isdigit() and len(code) == TOTP_CODE_DIGITS:
        return verify_app_code(user, code)
    return use_recovery_code(user, code)


def enable_two_factor(user):
    """Turns on the key ``start_setup`` gave ``user`` and returns their first
    recovery codes."""
    user.two_factor_enabled_at = timezone.now()
    user.save(update_fields=["two_factor_enabled_at"])
    return issue_recovery_codes(user)


def clear_two_factor(user):
    """Turns two-factor sign-in off for ``user`` and forgets their key and
    recovery codes."""
    RecoveryCode.objects.filter(user=user).delete()
    user.totp_secret = ""
    user.two_factor_enabled_at = None
    user.totp_last_used_step = None
    user.save(
        update_fields=["totp_secret", "two_factor_enabled_at", "totp_last_used_step"]
    )


def make_login_token(user):
    """Proof that ``user``'s password was just accepted, for the code step."""
    return signing.dumps({"user": user.pk}, salt=_LOGIN_SALT)


def login_token_user_id(token):
    """The id of the account a genuine sign-in token younger than
    ``TWO_FACTOR_LOGIN_TIMEOUT`` was issued for."""
    try:
        payload = signing.loads(
            token, salt=_LOGIN_SALT, max_age=TWO_FACTOR_LOGIN_TIMEOUT.total_seconds()
        )
    except signing.BadSignature:  # SignatureExpired is a BadSignature too.
        raise InvalidTwoFactorLoginError from None
    return payload["user"]


def read_login_token(token):
    """The account a sign-in token was issued for, while the token is valid
    and the account can still sign in with two-factor."""
    user = User.objects.filter(pk=login_token_user_id(token), is_active=True).first()
    if not user or not user.two_factor_enabled:
        raise InvalidTwoFactorLoginError
    return user
