from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from openpyxl import load_workbook

from users.choices import InvitationStatus
from users.constants import MAX_BULK_INVITE_ROWS
from users.models import Invitation
from users.serializers import InvitationCreateSerializer
from users.tasks import send_invitation_email_task


class BulkInviteLimitExceeded(Exception):
    """Raised when an uploaded file has more rows than allowed."""


def parse_invitation_emails(file):
    """Read a single-column .xlsx upload into a list of raw email strings,
    skipping a header row if present. Raises `BulkInviteLimitExceeded` if
    there are more than `MAX_BULK_INVITE_ROWS` rows."""

    workbook = load_workbook(file, read_only=True, data_only=True)
    worksheet = workbook.active

    values = [
        str(row[0]).strip()
        for row in worksheet.iter_rows(min_col=1, max_col=1, values_only=True)
        if row and row[0] is not None and str(row[0]).strip()
    ]

    if values and not _is_valid_email(values[0]):
        values = values[1:]

    if len(values) > MAX_BULK_INVITE_ROWS:
        raise BulkInviteLimitExceeded(
            f"file must contain at most {MAX_BULK_INVITE_ROWS} emails."
        )

    return values


def bulk_create_invitations(emails, request):
    """Create a pending Invitation for each valid, non-duplicate email via
    the same path as single invitation creation. Invalid, duplicate, or
    already-invited/existing-user emails are skipped and reported instead
    of failing the batch."""

    organization = request.user.organization
    created = []
    skipped = []
    seen = set()

    for raw_email in emails:
        email = raw_email.strip()
        normalized = email.lower()

        if not _is_valid_email(email):
            skipped.append({"email": raw_email, "reason": "invalid email"})
            continue

        if normalized in seen:
            skipped.append({"email": raw_email, "reason": "duplicate in file"})
            continue
        seen.add(normalized)

        if (
            get_user_model()
            .objects.filter(organization=organization, email__iexact=email)
            .exists()
        ):
            skipped.append(
                {"email": raw_email, "reason": "user already exists in organization"}
            )
            continue

        if (
            Invitation.objects.for_organization(organization)
            .filter(email__iexact=email, status=InvitationStatus.PENDING)
            .exists()
        ):
            skipped.append({"email": raw_email, "reason": "invitation already pending"})
            continue

        serializer = InvitationCreateSerializer(
            data={"email": email}, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save()
        send_invitation_email_task.delay(invitation.pk)
        created.append(invitation)

    return {"created": created, "skipped": skipped}


def _is_valid_email(value):
    try:
        validate_email(value)
    except ValidationError:
        return False
    return True
