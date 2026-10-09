"""Fixed magic numbers for the projects app.

Operational limits meant to be tuned per-environment belong in ``.env`` /
``core/settings``, not here. This module is only for values that are
part of the product's behaviour and don't change between deployments.
"""

MEGABYTE = 1024 * 1024
GIGABYTE = 1024 * MEGABYTE

# One attached file at most. nginx's body limit on the upload route sits a
# little above it, for the multipart wrapping (frontend/nginx).
MAX_ATTACHMENT_BYTES = 10 * MEGABYTE

# All of an organization's attached files together - including those of
# documents in the trash, which are still stored.
ORGANIZATION_ATTACHMENT_QUOTA_BYTES = 1 * GIGABYTE

# How much of a file's start is read to recognise its type.
FILE_SIGNATURE_BYTES = 16

MAX_ATTACHMENT_NAME_LENGTH = 255
