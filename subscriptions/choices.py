from django.db import models


class SubscriptionStatus(models.TextChoices):
    """The Stripe subscription statuses the app acts on - Stripe has more
    (trialing, unpaid, canceled, ...), which all mean no access here."""

    ACTIVE = "active", "Active"
    PAST_DUE = "past_due", "Past due"
