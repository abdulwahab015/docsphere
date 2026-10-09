from django.db import models
from django.utils import timezone

from audit.constants import AUDIT_EVENT_RETENTION
from audit.mappings import VERBS_BY_KIND
from projects.permissions import openable_by


class AuditEventQuerySet(models.QuerySet):
    def record(
        self, actor, verb, *, target_user=None, project=None, document=None, **details
    ):
        """Records that ``actor`` did ``verb`` in their organization - to
        ``target_user``, on ``project`` or ``document`` - with ``details``
        (levels, roles, an invited address, a file name). Call it in the same
        transaction as the change, after it's been made, so an action that
        fails records nothing."""
        return self.create(
            organization_id=actor.organization_id,
            actor=actor,
            verb=verb,
            target_user=target_user,
            project=project,
            document=document,
            details=details,
        )

    def for_organization(self, organization):
        return self.filter(organization=organization)

    def of_kind(self, kind):
        return self.filter(verb__in=VERBS_BY_KIND[kind])

    def with_resource_access(self, user):
        """Annotates ``resource_visible``: whether ``user`` could open the
        project or document the event is about. Events about none count as
        visible."""
        return self.annotate(
            resource_visible=models.Case(
                models.When(
                    project__isnull=False,
                    then=openable_by(user, "project"),
                ),
                models.When(
                    document__isnull=False,
                    then=openable_by(user, "document"),
                ),
                default=models.Value(True),
                output_field=models.BooleanField(),
            )
        )

    def expired(self):
        """Events older than the retention period."""
        return self.filter(created__lt=timezone.now() - AUDIT_EVENT_RETENTION)
