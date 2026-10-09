from datetime import timedelta

# How long a notification is kept, read or not, before the daily cleanup
# removes it.
NOTIFICATION_RETENTION = timedelta(days=90)
