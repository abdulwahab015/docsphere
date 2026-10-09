from celery import shared_task
from django.conf import settings
from django.utils import timezone

from core.email import email_task, send_templated_mail
from organizations.constants import EXPORT_LINK_EXPIRY
from organizations.exports import build_export, make_export_token
from organizations.models import Organization, OrganizationExport
from organizations.services import purge_organization

# Where the emailed export link opens, in the app.
EXPORT_DOWNLOAD_PATH = "/settings/organization/export"


@shared_task
def build_organization_export_task(export_id):
    """Builds the .zip an admin asked for, then emails them the link."""
    export = OrganizationExport.objects.select_related(
        "organization", "requested_by"
    ).get(pk=export_id)
    build_export(export)
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
