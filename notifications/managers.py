from django.db import models
from django.utils import timezone

from notifications.constants import NOTIFICATION_RETENTION
from projects.permissions import openable_by


class NotificationQuerySet(models.QuerySet):
    def notify(
        self, recipients, actor, verb, *, project=None, document=None, **details
    ):
        """Tells each of ``recipients`` that ``actor`` did ``verb`` - on
        ``project`` or ``document``, with ``details`` such as the level given.
        Nobody is told about their own action. Call it in the same
        transaction as the change, so a failed action tells no one."""
        return self.bulk_create(
            self.model(
                recipient=recipient,
                actor=actor,
                verb=verb,
                project=project,
                document=document,
                details=details,
            )
            for recipient in recipients
            if recipient.pk != actor.pk
        )

    def for_recipient(self, user):
        return self.filter(recipient=user)

    def unread(self):
        return self.filter(read_at__isnull=True)

    def with_resource_access(self, user):
        """Annotates ``resource_visible``: whether ``user`` can still open the
        project or document - access may have been taken away, or it made
        private, since they were told. Notifications about none count as
        visible."""
        return self.annotate(
            resource_visible=models.Case(
                models.When(project__isnull=False, then=openable_by(user, "project")),
                models.When(document__isnull=False, then=openable_by(user, "document")),
                default=models.Value(True),
                output_field=models.BooleanField(),
            )
        )

    def mark_read(self):
        """Marks the unread ones read, now; returns how many."""
        return self.unread().update(read_at=timezone.now())

    def expired(self):
        """Notifications older than the retention period, read or not."""
        return self.filter(created__lt=timezone.now() - NOTIFICATION_RETENTION)
