"""Scheduled-task stubs for subscription lifecycle emails.

No task queue is wired up yet (no Celery/beat in requirements.txt) — these
are plain functions to be hooked into a scheduler later.
"""


def send_expiry_reminder_emails():
    """Email organization admins whose subscription is expiring soon.

    TODO: query djstripe.models.Subscription.objects.filter(status="active",
    current_period_end__lte=<soon threshold>) and notify each organization's
    admins via the configured EMAIL_BACKEND.
    """
    raise NotImplementedError
