from django.conf import settings
from django.db import models

from core.models import TimeStampedModel
from notifications.choices import NotificationVerb
from notifications.managers import NotificationQuerySet


class Notification(TimeStampedModel):
    """Something that happened that its recipient should know about: they
    were shared with, someone asked to edit their document, or their request
    was answered. Shown in the app beside the email about the same thing;
    kept for 90 days."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="notifications_caused",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    document = models.ForeignKey(
        "projects.Document",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )

    verb = models.CharField(max_length=30, choices=NotificationVerb.choices)
    # ``access_level`` for a share or a changed level.
    details = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        indexes = [models.Index(fields=["recipient", "-created"])]

    def __str__(self):
        return f"{self.recipient} - {self.get_verb_display()}"
