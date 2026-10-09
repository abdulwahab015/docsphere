from celery import shared_task

from notifications.models import Notification


@shared_task
def remove_expired_notifications_task():
    """Daily: deletes notifications older than the retention period."""
    Notification.objects.expired().delete()
