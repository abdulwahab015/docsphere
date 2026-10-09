from celery import shared_task
from django.conf import settings
from django.utils import timezone

from core.email import email_task, send_templated_mail
from organizations.choices import ExportStatus
from organizations.constants import (
    EXPORT_LINK_EXPIRY,
    EXPORT_MAX_RETRIES,
    EXPORT_RETRY_BACKOFF_SECONDS,
)
from organizations.exports import build_export, make_export_token
from organizations.models import Organization, OrganizationExport
from organizations.services import purge_organization

# Where the emailed export link opens, in the app, and where a new one is
# asked for.
EXPORT_DOWNLOAD_PATH = "/settings/organization/export"
ORGANIZATION_SETTINGS_PATH = "/settings/organization"


@shared_task(bind=True, max_retries=EXPORT_MAX_RETRIES)
def build_organization_export_task(self, export_id):
    """Builds the .zip an admin asked for, then emails them the link. A
    failed build is tried again with growing waits; once the retries are
    used up the export is marked failed - so the admin may ask again - and
    they're told. The error is raised again either way, so it's reported."""
    export = OrganizationExport.objects.select_related(
        "organization", "requested_by"
    ).get(pk=export_id)
    try:
        build_export(export)
    except Exception as error:
        if self.request.retries < self.max_retries:
            raise self.retry(
                exc=error,
                countdown=EXPORT_RETRY_BACKOFF_SECONDS * 2**self.request.retries,
            ) from error
        export.status = ExportStatus.FAILED
        export.save(update_fields=["status", "modified"])
        send_export_failed_email_task.delay(export.pk)
        raise

    export.status = ExportStatus.READY
    export.save(update_fields=["status", "modified"])
    send_export_ready_email_task.delay(export.pk)


@email_task
def send_export_ready_email_task(export_id):
    export = OrganizationExport.objects.select_related(
        "organization", "requested_by"
    ).get(pk=export_id)

    send_templated_mail(
        "organizations/email/export_ready",
        {
            "organization_name": export.organization.name,
            "download_url": (
                f"{settings.FRONTEND_URL}{EXPORT_DOWNLOAD_PATH}"
                f"?token={make_export_token(export)}"
            ),
            "days": EXPORT_LINK_EXPIRY.days,
        },
        [export.requested_by.email],
    )


@email_task
def send_export_failed_email_task(export_id):
    export = OrganizationExport.objects.select_related(
        "organization", "requested_by"
    ).get(pk=export_id)

    send_templated_mail(
        "organizations/email/export_failed",
        {
            "organization_name": export.organization.name,
            "settings_url": f"{settings.FRONTEND_URL}{ORGANIZATION_SETTINGS_PATH}",
        },
        [export.requested_by.email],
    )


@shared_task
def remove_expired_exports_task():
    """Daily: deletes exports, and their stored files, once their link has
    expired."""
    expired = OrganizationExport.objects.filter(
        created__lt=timezone.now() - EXPORT_LINK_EXPIRY
    )
    stored_files = [
        (export.file.storage, export.file.name) for export in expired.exclude(file="")
    ]
    expired.delete()
    for storage, name in stored_files:
        storage.delete(name)


@shared_task
def purge_deleted_organizations_task():
    """Daily: removes organizations deleted longer ago than they can be
    restored, with everything in them."""
    for organization in Organization.objects.due_for_purge():
        purge_organization(organization)
