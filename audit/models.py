from django.conf import settings
from django.db import models

from audit.choices import AuditVerb
from audit.managers import AuditEventQuerySet
from core.models import TimeStampedModel


class AuditEvent(TimeStampedModel):
    """Something done in an organization that its admins can look back on:
    who changed access to what, membership, deletes and restores, attached
    files. Written once, in the same transaction as the change itself, and
    never edited; kept for a year.

    The people and resources are references, so the activity list shows
    their current names. Users and resources are only ever deactivated or
    trashed, never deleted, so an event outlives an account only when the
    whole organization goes - ``SET_NULL`` covers that rather than blocking
    it."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_events",
    )
    # The person the action was about: shared with, given a role, deactivated.
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events_about",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    document = models.ForeignKey(
        "projects.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )

    verb = models.CharField(max_length=30, choices=AuditVerb.choices)
    # What changed, by verb: ``access_level``/``previous_access_level``,
    # ``visibility``, ``role``/``previous_role``, an invitation's ``email``,
    # an attachment's ``file_name`` and ``size``.
    details = models.JSONField(default=dict, blank=True)

    objects = AuditEventQuerySet.as_manager()

    class Meta:
        indexes = [models.Index(fields=["organization", "-created"])]

    def __str__(self):
        return f"{self.actor} - {self.get_verb_display()}"
