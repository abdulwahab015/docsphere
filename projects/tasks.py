from celery import shared_task

from core.email import send_templated_mail
from projects.models import DocumentPermission, ProjectPermission


@shared_task
def send_project_shared_email_task(permission_id):
    permission = ProjectPermission.objects.select_related("project", "user").get(
        pk=permission_id
    )

    send_templated_mail(
        "projects/email/project_shared",
        {
            "project_name": permission.project.name,
            "access_level": permission.get_access_level_display(),
        },
        [permission.user.email],
    )


@shared_task
def send_document_shared_email_task(permission_id):
    permission = DocumentPermission.objects.select_related("document", "user").get(
        pk=permission_id
    )

    send_templated_mail(
        "projects/email/document_shared",
        {
            "document_title": permission.document.title,
            "access_level": permission.get_access_level_display(),
        },
        [permission.user.email],
    )
