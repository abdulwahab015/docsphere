"""Fixed magic numbers for the users app.

Operational limits meant to be tuned per-environment belong in ``.env`` /
``core/settings``, not here. This module is only for values that are
part of the code's behaviour and don't change between deployments.
"""

MAX_PENDING_INVITATIONS_PER_ORG = 100

INVITATION_TOKEN_BYTES = 32

MAX_PASSWORD_LENGTH = 128

MAX_BULK_INVITE_ROWS = 500
