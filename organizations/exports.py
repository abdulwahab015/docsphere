"""An organization's data as a .zip for its admins: who's in it, and the
projects and documents (with their text, sharing and attached files) that
the admin asking could open. Private things they can't open are counted,
never included - an export is no way around the privacy rule.

Also the signed tokens in the emailed download link."""

import json
import zipfile
from tempfile import TemporaryFile

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.files import File
from django.utils import timezone

from organizations.constants import EXPORT_LINK_EXPIRY
from projects.models import Document, Project

User = get_user_model()

_EXPORT_SALT = "organizations.export-download"
INVALID_EXPORT_LINK_MESSAGE = (
    "This download link is invalid or has expired. Ask for a new export."
)


class InvalidExportLinkError(Exception):
    pass


def make_export_token(export):
    return signing.dumps(export.pk, salt=_EXPORT_SALT)


def read_export_token(token):
    """The export id a link's token names, if it's genuine and no older
    than ``EXPORT_LINK_EXPIRY``."""
    try:
        return signing.loads(
            token,
            salt=_EXPORT_SALT,
            max_age=EXPORT_LINK_EXPIRY.total_seconds(),
        )
    except signing.BadSignature as error:
        raise InvalidExportLinkError from error


def _shares(resource):
    return [
        {"email": permission.user.email, "access_level": permission.access_level}
        for permission in resource.permissions.all()
    ]


def _members(organization):
    return [
        {
            "email": member.email,
            "name": member.name,
            "role": member.org_role,
            "active": member.is_active,
            "joined": member.created.isoformat(),
        }
        for member in User.objects.filter(organization=organization).order_by("email")
    ]


def _projects(projects):
    return [
        {
            "name": project.name,
            "description": project.description,
            "visibility": project.visibility,
            "created_by": project.created_by.email,
            "created": project.created.isoformat(),
            "shared_with": _shares(project),
        }
        for project in projects
    ]


def _attachment_path(attachment):
    return f"attachments/{attachment.document_id}/{attachment.pk}-{attachment.name}"


def _documents(documents):
    return [
        {
            "title": document.title,
            "project": document.project.name if document.project else None,
            "content": document.content,
            "visibility": document.visibility,
            "revision": document.revision,
            "created_by": document.created_by.email,
            "created": document.created.isoformat(),
            "modified": document.modified.isoformat(),
            "shared_with": _shares(document),
            "attachments": [
                _attachment_path(attachment)
                for attachment in document.attachments.all()
            ],
        }
        for document in documents
    ]


def _write_json(archive, name, data):
    archive.writestr(name, json.dumps(data, indent=2, ensure_ascii=False))


def build_export(export):
    """Writes the .zip for ``export`` and stores it on the row."""
    organization = export.organization
    admin = export.requested_by
    projects = (
        Project.objects.visible_to(admin)
        .select_related("created_by")
        .prefetch_related("permissions__user")
        .order_by("name")
    )
    documents = (
        Document.objects.visible_to(admin)
        .select_related("created_by", "project")
        .prefetch_related("permissions__user", "attachments")
        .order_by("title")
    )

    with TemporaryFile() as buffer:
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            _write_json(
                archive,
                "organization.json",
                {
                    "name": organization.name,
                    "billing_email": organization.billing_email,
                    "exported_at": timezone.now().isoformat(),
                    "exported_by": admin.email,
                    "not_included": {
                        "private_projects": Project.objects.for_organization(
                            organization
                        ).count()
                        - len(projects),
                        "private_documents": Document.objects.for_organization(
                            organization
                        ).count()
                        - len(documents),
                    },
                },
            )
            _write_json(archive, "members.json", _members(organization))
            _write_json(archive, "projects.json", _projects(projects))
            _write_json(archive, "documents.json", _documents(documents))
            for document in documents:
                for attachment in document.attachments.all():
                    with attachment.file.open("rb") as stored:
                        archive.writestr(_attachment_path(attachment), stored.read())
        buffer.seek(0)
        export.file.save("export.zip", File(buffer))
