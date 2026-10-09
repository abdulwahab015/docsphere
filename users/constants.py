"""Fixed magic numbers for the users app.

Operational limits meant to be tuned per-environment belong in ``.env`` /
``core/settings``, not here. This module is only for values that are
part of the code's behaviour and don't change between deployments.
"""

MAX_PENDING_INVITATIONS_PER_ORG = 100

INVITATION_TOKEN_BYTES = 32

MAX_PASSWORD_LENGTH = 128

# The same cap Django gives its own first and last name fields.
MAX_NAME_LENGTH = 150

MAX_BULK_INVITE_ROWS = 500

# How a deleted account is shown wherever it's still named (as the author of
# a document, the sender of an invitation, ...).
DELETED_USER_NAME = "Deleted user"
