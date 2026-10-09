from datetime import timedelta

# How long an audit event is kept before the daily cleanup removes it.
AUDIT_EVENT_RETENTION = timedelta(days=365)
