"""Fixed magic numbers for the users app.

Operational limits meant to be tuned per-environment belong in ``.env`` /
``core/settings``, not here. This module is only for values that are
part of the code's behaviour and don't change between deployments.
"""

from datetime import timedelta

MAX_PENDING_INVITATIONS_PER_ORG = 100

INVITATION_TOKEN_BYTES = 32

MAX_PASSWORD_LENGTH = 128

# The same cap Django gives its own first and last name fields.
MAX_NAME_LENGTH = 150

MAX_BULK_INVITE_ROWS = 500

# How a deleted account is shown wherever it's still named (as the author of
# a document, the sender of an invitation, ...).
DELETED_USER_NAME = "Deleted user"

# Two-factor sign-in with an authenticator app (TOTP). The name the app lists
# the account under, beside the person's email address.
TWO_FACTOR_ISSUER = "DocSphere"
# pyotp's default key length: 32 base32 characters, 160 bits.
TOTP_SECRET_LENGTH = 32
TOTP_CODE_DIGITS = 6
# A code from the time step either side of now is accepted too, for a phone
# whose clock is a little off.
TOTP_VALID_WINDOW = 1
# How long someone has, after their password is accepted, to enter a code.
TWO_FACTOR_LOGIN_TIMEOUT = timedelta(minutes=5)
# Longer than any code or recovery code, so an oversized value is refused
# before anything is hashed.
MAX_TWO_FACTOR_CODE_LENGTH = 32

# One-time codes for signing in without the authenticator app, shown once.
RECOVERY_CODE_COUNT = 10
# 10 characters from 31 (no 0/o, 1/l/i lookalikes): about 50 bits each.
RECOVERY_CODE_LENGTH = 10
RECOVERY_CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
