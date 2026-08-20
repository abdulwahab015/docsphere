from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from openpyxl import load_workbook
from rest_framework import serializers as drf_serializers

from users.api.v1.serializers import InvitationCreateSerializer
from users.choices import InvitationStatus
from users.models import Invitation
from users.tasks import send_invitation_email_task


def parse_invitation_emails(file):
    """Read a single-column .xlsx upload of email addresses.

    Returns the raw, stripped cell values in order. A header row is skipped
    if the first cell isn't itself a valid email address. Validation beyond
    that (malformed addresses, duplicates, existing users/invitations) is
    left to `bulk_create_invitations`, which needs to report per-row reasons.
    """
    workbook = load_workbook(file, read_only=True, data_only=True)
    worksheet = workbook.active

    values = [
        str(row[0]).strip()
        for row in worksheet.iter_rows(min_col=1, max_col=1, values_only=True)
        if row and row[0] is not None and str(row[0]).strip()
    ]

    if values and not _is_valid_email(values[0]):
        values = values[1:]

    return values


def bulk_create_invitations(emails, request):
    """Create a pending Invitation for each valid, non-duplicate email via
    the same path as single invitation creation. Invalid, duplicate,
    already-invited/existing-user emails, and rows rejected by
    `InvitationCreateSerializer` (e.g. the org's pending-invitation cap)
    are skipped and reported instead of failing the batch."""
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
        try:
            serializer.is_valid(raise_exception=True)
        except drf_serializers.ValidationError as exc:
            skipped.append({"email": raw_email, "reason": _first_error_message(exc)})
            continue

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


def _first_error_message(exc):
    """Flatten a DRF ValidationError's (possibly nested) detail down to one
    readable string, for the per-row skip reason."""
    detail = exc.detail
    while isinstance(detail, list | dict):
        detail = next(iter(detail.values())) if isinstance(detail, dict) else detail[0]
    return str(detail)
