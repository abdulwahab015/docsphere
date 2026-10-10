from datetime import timedelta

# How long a deleted organization can still be restored by its admins before
# the daily purge removes it and everything in it.
ORGANIZATION_PURGE_DELAY = timedelta(days=30)

# How long an export can be downloaded from the link emailed for it; the
# daily clean-up removes it afterwards.
EXPORT_LINK_EXPIRY = timedelta(days=7)

# An export still marked as building after this long is taken to have died
# with its worker, so it no longer blocks asking for another.
EXPORT_BUILD_TIMEOUT = timedelta(hours=1)
# A failed build is tried again this many times, waiting twice as long each
# time from the first delay, before the admin is told it failed.
EXPORT_MAX_RETRIES = 3
EXPORT_RETRY_BACKOFF_SECONDS = 60
