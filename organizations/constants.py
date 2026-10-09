from datetime import timedelta

# How long a deleted organization can still be restored by its admins before
# the daily purge removes it and everything in it.
ORGANIZATION_PURGE_DELAY = timedelta(days=30)

# How long an export can be downloaded from the link emailed for it; the
# daily clean-up removes it afterwards.
EXPORT_LINK_EXPIRY = timedelta(days=7)
