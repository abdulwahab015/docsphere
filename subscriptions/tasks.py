from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from djstripe.models import Subscription

from core.email import send_templated_mail
from organizations.models import Organization


@shared_task
def send_expiry_reminders_task():
    """Dispatches a reminder email for every organization whose active
    subscription is due to renew within SUBSCRIPTION_EXPIRY_REMINDER_DAYS and
    hasn't already been reminded for the current period.
    """
    now = timezone.now()
    window_end = now + timedelta(days=settings.SUBSCRIPTION_EXPIRY_REMINDER_DAYS)

    expiring_subscriptions = (
        Subscription.objects.active()
        .filter(
            stripe_data__current_period_end__gte=int(now.timestamp()),
            stripe_data__current_period_end__lte=int(window_end.timestamp()),
        )
        .select_related("customer")
    )

    organization_ids = {
        subscription.customer.subscriber_id
        for subscription in expiring_subscriptions
        if subscription.customer and subscription.customer.subscriber_id
    }

    organizations = Organization.objects.filter(
        id__in=organization_ids,
        is_active=True,
        last_expiry_reminder_sent_at__isnull=True,
    )

    for organization in organizations:
        send_expiry_reminder_email_task.delay(organization.pk)


@shared_task
def send_expiry_reminder_email_task(organization_id):
    organization = Organization.objects.get(pk=organization_id)
    subscription = organization.active_subscription

    send_templated_mail(
        "subscriptions/email/expiry_reminder",
        {
            "organization_name": organization.name,
            "expiry_date": subscription.current_period_end.strftime("%Y-%m-%d"),
        },
        [organization.email],
    )

    organization.last_expiry_reminder_sent_at = timezone.now()
    organization.save(update_fields=["last_expiry_reminder_sent_at"])
