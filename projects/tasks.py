from celery import shared_task

from core.email import send_templated_mail
from projects.models import DocumentPermission, ProjectPermission


def _send_share_notification(
    permission_model,
    resource_field,
    resource_name_attr,
    permission_id,
    template_prefix,
    context_key,
):
    permission = permission_model.objects.select_related(resource_field, "user").get(
        pk=permission_id
    )
    resource = getattr(permission, resource_field)

    send_templated_mail(
        template_prefix,
        {
            context_key: getattr(resource, resource_name_attr),
            "access_level": permission.get_access_level_display(),
        },
        [permission.user.email],
    )


@shared_task
def send_project_shared_email_task(permission_id):
    _send_share_notification(
        ProjectPermission,
        "project",
        "name",
        permission_id,
        "projects/email/project_shared",
        "project_name",
    )


@shared_task
def send_document_shared_email_task(permission_id):
    _send_share_notification(
        DocumentPermission,
        "document",
        "title",
        permission_id,
        "projects/email/document_shared",
        "document_title",
    )
