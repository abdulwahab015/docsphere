from celery import shared_task
from django.core.mail import send_mail
from django.core.mail.backends import console
from django.template import Context
from django.template.loader import get_template

# A failed send is retried up to 5 times, waiting up to 1, 2, 4, 8 and 10
# minutes (jittered), to ride out a mail server or network outage of up to
# about half an hour.
EMAIL_RETRY_BACKOFF_SECONDS = 60
EMAIL_RETRY_BACKOFF_MAX_SECONDS = 600
EMAIL_MAX_RETRIES = 5


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


def email_task(task_function):
    """Declares a Celery task that sends email, retried with exponential
    backoff when sending fails - the mail server or the network being briefly
    unavailable shouldn't lose an invitation or a notification. SMTP errors
    are ``OSError`` subclasses, like connection and timeout errors. Anything
    else (e.g. the row it was about no longer exists) fails at once: trying
    again wouldn't change the outcome."""
    return shared_task(
        autoretry_for=(OSError,),
        retry_backoff=EMAIL_RETRY_BACKOFF_SECONDS,
        retry_backoff_max=EMAIL_RETRY_BACKOFF_MAX_SECONDS,
        max_retries=EMAIL_MAX_RETRIES,
    )(task_function)


class ConsoleEmailBackend(console.EmailBackend):
    """Prints each email as it was written, for local development.

    Django's own console backend prints the encoded message, and a text body
    with a line over 78 characters is encoded quoted-printable: every link
    then shows as ``token=3D...``, broken across two lines, and can't be
    pasted into a browser. A mail client decodes that; a terminal doesn't.
    """

    def write_message(self, message):
        self.stream.write(
            f"From: {message.from_email}\n"
            f"To: {', '.join(message.to)}\n"
            f"Subject: {message.subject}\n\n"
            f"{message.body}\n"
        )
        self.stream.write("-" * 79 + "\n")
