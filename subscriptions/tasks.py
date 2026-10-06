from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from djstripe.models import Subscription

from core.email import email_task, send_templated_mail
from organizations.models import Organization
from subscriptions.utils import cancels_at_period_end, get_period_end


@shared_task
def send_expiry_reminders_task():
    """Dispatches a reminder email for every organization whose active
    subscription's billing period ends within SUBSCRIPTION_EXPIRY_REMINDER_DAYS
    - whether it renews then or, once cancelled, ends - and that hasn't
    already been reminded for the current billing period. An organization
    with no billing email has nowhere to send it.
    """
    now = timezone.now()
    window = timedelta(days=settings.SUBSCRIPTION_EXPIRY_REMINDER_DAYS)

    subscriptions = Subscription.objects.active().select_related("customer__subscriber")

    due_organization_ids = set()
    for subscription in subscriptions:
        organization = subscription.customer and subscription.customer.subscriber
        period_end = get_period_end(subscription)
        if (
            not organization
            or not organization.is_active
            or not organization.email
            or not period_end
        ):
            continue
        if not now <= period_end <= now + window:
            continue
        last_sent = organization.last_expiry_reminder_sent_at
        if not last_sent or last_sent < period_end - window:
            due_organization_ids.add(organization.pk)

    for organization_id in due_organization_ids:
        send_expiry_reminder_email_task.delay(organization_id)


@email_task
def send_expiry_reminder_email_task(organization_id):
    """Says the subscription renews on its period end, or - once it has been
    cancelled - that it ends then, with a link to billing either way."""
    organization = Organization.objects.get(pk=organization_id)
    subscription = organization.active_subscription
    if not subscription:
        return

    template = (
        "subscriptions/email/subscription_ending"
        if cancels_at_period_end(subscription)
        else "subscriptions/email/subscription_renewing"
    )
    send_templated_mail(
        template,
        {
            "organization_name": organization.name,
            "period_end": get_period_end(subscription).strftime("%Y-%m-%d"),
            "billing_url": f"{settings.FRONTEND_URL}/billing/",
        },
        [organization.email],
    )

    organization.last_expiry_reminder_sent_at = timezone.now()
    organization.save(update_fields=["last_expiry_reminder_sent_at"])
