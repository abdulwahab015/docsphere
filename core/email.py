from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_templated_mail(template_prefix, context, recipient_list):
    """Render ``<prefix>.subject.txt`` + ``<prefix>.body.txt`` and send as
    plain text from ``DEFAULT_FROM_EMAIL``.

    Keeps message wording in template files rather than inline in each task.
    The subject template is ``.strip()``-ed so a trailing newline in the file
    never leaks into the header.
    """
    subject = render_to_string(f"{template_prefix}.subject.txt", context).strip()
    body = render_to_string(f"{template_prefix}.body.txt", context)

    send_mail(
        subject=subject,
        message=body,
        from_email=None,
        recipient_list=recipient_list,
    )
