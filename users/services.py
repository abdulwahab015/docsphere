import secrets
from zipfile import BadZipFile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from users.choices import InvitationStatus
from users.constants import (
    INVITATION_TOKEN_BYTES,
    MAX_BULK_INVITE_ROWS,
    MAX_PENDING_INVITATIONS_PER_ORG,
)
from users.models import Invitation
from users.tasks import send_invitation_email_task

User = get_user_model()


def parse_invitation_emails(file):
    """Read a single-column .xlsx upload into a list of raw email strings,
    skipping a header row if present. Raises `ValueError` if the file isn't
    a readable .xlsx workbook, or has more than `MAX_BULK_INVITE_ROWS` rows."""
    try:
        workbook = load_workbook(file, read_only=True, data_only=True)
    except (BadZipFile, KeyError, InvalidFileException) as exc:
        raise ValueError("file must be a valid .xlsx workbook.") from exc

    worksheet = workbook.active

    emails = [
        str(cell_value).strip()
        for (cell_value,) in worksheet.iter_rows(min_col=1, max_col=1, values_only=True)
        if cell_value is not None and str(cell_value).strip()
    ]

    if emails and "@" not in emails[0]:
        emails = emails[1:]

    if len(emails) > MAX_BULK_INVITE_ROWS:
        raise ValueError(f"file must contain at most {MAX_BULK_INVITE_ROWS} emails.")

    return emails


def create_invitation(*, organization, invited_by, email):
    """Create a pending Invitation with a freshly generated token. Shared by the
    single-invite endpoint and the bulk upload so both produce identical rows."""
    return Invitation.objects.create(
        organization=organization,
        invited_by=invited_by,
        email=email,
        token=secrets.token_urlsafe(INVITATION_TOKEN_BYTES),
    )


def bulk_create_invitations(emails, *, organization, invited_by):
    """Create a pending Invitation for each usable email. Rows that are malformed,
    over-long, duplicated in the file, already a user or a pending invite in the
    org, or past the org's pending-invitation cap are skipped and reported rather
    than failing the batch."""
    max_email_length = Invitation._meta.get_field("email").max_length
    candidate_emails = {raw.strip().lower() for raw in emails}

    existing_user_emails = {
        stored.lower()
        for stored in User.objects.filter(
            organization=organization, email__in=candidate_emails
        ).values_list("email", flat=True)
    }

    pending_invites = Invitation.objects.for_organization(organization).filter(
        status=InvitationStatus.PENDING
    )
    pending_invite_emails = {
        stored.lower()
        for stored in pending_invites.filter(email__in=candidate_emails).values_list(
            "email", flat=True
        )
    }
    remaining_slots = MAX_PENDING_INVITATIONS_PER_ORG - pending_invites.count()

    created_invitations = []
    skipped_rows = []
    seen_emails = set()

    for original_email in emails:
        email = original_email.strip()
        normalized_email = email.lower()

        try:
            validate_email(email)
        except ValidationError:
            skipped_rows.append({"email": original_email, "reason": "invalid email"})
            continue

        if len(email) > max_email_length:
            skipped_rows.append({"email": original_email, "reason": "email too long"})
            continue

        if normalized_email in seen_emails:
            skipped_rows.append(
                {"email": original_email, "reason": "duplicate in file"}
            )
            continue
        seen_emails.add(normalized_email)

        if normalized_email in existing_user_emails:
            skipped_rows.append(
                {
                    "email": original_email,
                    "reason": "user already exists in organization",
                }
            )
            continue

        if normalized_email in pending_invite_emails:
            skipped_rows.append(
                {"email": original_email, "reason": "invitation already pending"}
            )
            continue

        if remaining_slots <= 0:
            skipped_rows.append(
                {
                    "email": original_email,
                    "reason": "organization has too many pending invitations",
                }
            )
            continue

        invitation = create_invitation(
            organization=organization, invited_by=invited_by, email=email
        )
        remaining_slots -= 1
        send_invitation_email_task.delay(invitation.pk)
        created_invitations.append(invitation)

    return {"created": created_invitations, "skipped": skipped_rows}
