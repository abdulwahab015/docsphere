from celery import shared_task

from audit.models import AuditEvent


@shared_task
def remove_expired_audit_events_task():
    """Daily: deletes audit events older than the retention period."""
    AuditEvent.objects.expired().delete()
