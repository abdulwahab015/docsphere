from django.core.mail import send_mail
from django.template import Context
from django.template.loader import get_template


def _render_plain(template_name, context):
    """Renders a template with autoescaping off.

    Django's template engine HTML-escapes by default regardless of the
    ``.txt`` extension, which would otherwise turn a `&` in an interpolated
    URL's query string into `&amp;` in a plain-text email body.
    """
    return get_template(template_name).template.render(
        Context(context, autoescape=False)
    )


def send_templated_mail(template_prefix, context, recipient_list):
    """Render ``<prefix>.subject.txt`` + ``<prefix>.body.txt`` and send as
    plain text from ``DEFAULT_FROM_EMAIL``.

    Keeps message wording in template files rather than inline in each task.
    The subject template is ``.strip()``-ed so a trailing newline in the file
    never leaks into the header.
    """
    subject = _render_plain(f"{template_prefix}.subject.txt", context).strip()
    body = _render_plain(f"{template_prefix}.body.txt", context)

    send_mail(
        subject=subject,
        message=body,
        from_email=None,
        recipient_list=recipient_list,
    )
