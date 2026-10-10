from core.email import email_task, send_templated_mail
from projects.models import DocumentAccessRequest, DocumentPermission, ProjectPermission
from projects.permissions import active_owners


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


@email_task
def send_project_shared_email_task(permission_id):
    _send_share_notification(
        ProjectPermission,
        "project",
        "name",
        permission_id,
        "projects/email/project_shared",
        "project_name",
    )


@email_task
def send_document_shared_email_task(permission_id):
    _send_share_notification(
        DocumentPermission,
        "document",
        "title",
        permission_id,
        "projects/email/document_shared",
        "document_title",
    )


@email_task
def send_access_request_created_email_task(access_request_id):
    access_request = DocumentAccessRequest.objects.select_related(
        "document", "requested_by"
    ).get(pk=access_request_id)
    owner_emails = list(
        active_owners(access_request.document).values_list("email", flat=True)
    )
    if not owner_emails:
        return

    send_templated_mail(
        "projects/email/access_request_created",
        {
            "document_title": access_request.document.title,
            "requested_by": access_request.requested_by.name_and_email,
        },
        owner_emails,
    )


@email_task
def send_access_request_approved_email_task(access_request_id):
    access_request = DocumentAccessRequest.objects.select_related(
        "document", "requested_by"
    ).get(pk=access_request_id)
    send_templated_mail(
        "projects/email/access_request_approved",
        {"document_title": access_request.document.title},
        [access_request.requested_by.email],
    )


@email_task
def send_access_request_denied_email_task(access_request_id):
    access_request = DocumentAccessRequest.objects.select_related(
        "document", "requested_by"
    ).get(pk=access_request_id)
    send_templated_mail(
        "projects/email/access_request_denied",
        {"document_title": access_request.document.title},
        [access_request.requested_by.email],
    )
