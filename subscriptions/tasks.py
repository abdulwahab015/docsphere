from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from djstripe.models import Subscription

from core.email import send_templated_mail
from organizations.models import Organization
from subscriptions.utils import get_period_end


@shared_task
def send_expiry_reminders_task():
    """Dispatches a reminder email for every organization whose active
    subscription is due to renew within SUBSCRIPTION_EXPIRY_REMINDER_DAYS and
    hasn't already been reminded for the current billing period.
    """
    now = timezone.now()
    window = timedelta(days=settings.SUBSCRIPTION_EXPIRY_REMINDER_DAYS)

    subscriptions = Subscription.objects.active().select_related("customer__subscriber")

    due_organization_ids = set()
    for subscription in subscriptions:
        organization = subscription.customer and subscription.customer.subscriber
        period_end = get_period_end(subscription)
        if not organization or not organization.is_active or not period_end:
            continue
        if not now <= period_end <= now + window:
            continue
        last_sent = organization.last_expiry_reminder_sent_at
        if not last_sent or last_sent < period_end - window:
            due_organization_ids.add(organization.pk)

    for organization_id in due_organization_ids:
        send_expiry_reminder_email_task.delay(organization_id)


@shared_task
def send_expiry_reminder_email_task(organization_id):
    organization = Organization.objects.get(pk=organization_id)
    subscription = organization.active_subscription
    if not subscription:
        return

    send_templated_mail(
        "subscriptions/email/expiry_reminder",
        {
            "organization_name": organization.name,
            "expiry_date": get_period_end(subscription).strftime("%Y-%m-%d"),
        },
        [organization.email],
    )

    organization.last_expiry_reminder_sent_at = timezone.now()
    organization.save(update_fields=["last_expiry_reminder_sent_at"])
