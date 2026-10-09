from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError

from users.constants import MAX_PASSWORD_LENGTH


def validate_current_password(user, password):
    """Proves a signed-in user is really them before a sensitive change.
    An over-long password is refused before it reaches the hasher."""
    if len(password) > MAX_PASSWORD_LENGTH or not user.check_password(password):
        raise ValidationError("Current password is incorrect.")
    return password


def validate_password_for_field(field_name, password, user=None):
    """Runs the password policy and reports any failure against
    ``field_name``, so a client can show it under the password input rather
    than as a form-wide ``non_field_errors`` message.

    Called from ``validate()`` rather than a ``validate_<field>`` hook because
    some callers only know ``user`` (for the similarity check) after
    validating other fields first."""
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise ValidationError({field_name: list(exc.messages)}) from exc
