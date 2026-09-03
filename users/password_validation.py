import re

from django.core.exceptions import ValidationError

from users.constants import MAX_PASSWORD_LENGTH

_SPECIAL_CHARS = re.compile(r"[!@#$%^&*()_+\-=\[\]{};:'\"\\|,.<>/?~`]")


class MaximumLengthValidator:
    def __init__(self, max_length=MAX_PASSWORD_LENGTH):
        self.max_length = max_length

    def validate(self, password, user=None):
        if len(password) > self.max_length:
            raise ValidationError(
                f"Password must be at most {self.max_length} characters.",
                code="password_too_long",
            )

    def get_help_text(self):
        return f"Your password must be at most {self.max_length} characters."


class ComplexityValidator:
    """Require a mix of character classes.

    Sits after Django's built-in length/common-password checks in
    ``AUTH_PASSWORD_VALIDATORS``; those still own minimum length.
    """

    def validate(self, password, user=None):
        missing = []
        if not any(c.islower() for c in password):
            missing.append("a lowercase letter")
        if not any(c.isupper() for c in password):
            missing.append("an uppercase letter")
        if not any(c.isdigit() for c in password):
            missing.append("a digit")
        if not _SPECIAL_CHARS.search(password):
            missing.append("a special character")

        if missing:
            raise ValidationError(
                "Password must contain " + ", ".join(missing) + ".",
                code="password_too_simple",
            )

    def get_help_text(self):
        return (
            "Your password must contain at least one lowercase letter, one uppercase "
            "letter, one digit, and one special character."
        )
