from django.db import models


class NotificationVerb(models.TextChoices):
    """What a notification tells its recipient."""

    ACCESS_GRANTED = "ACCESS_GRANTED", "Shared with you"
    ACCESS_CHANGED = "ACCESS_CHANGED", "Your access changed"
    ACCESS_REQUESTED = "ACCESS_REQUESTED", "Edit access requested"
    ACCESS_REQUEST_APPROVED = "ACCESS_REQUEST_APPROVED", "Your request was approved"
    ACCESS_REQUEST_DENIED = "ACCESS_REQUEST_DENIED", "Your request was denied"
