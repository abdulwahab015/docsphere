import secrets
from zipfile import BadZipFile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from audit.choices import AuditVerb
from audit.models import AuditEvent
from notifications.models import Notification
from projects.choices import AccessRequestStatus
from projects.models import (
    Document,
    DocumentAccessRequest,
    DocumentPermission,
    Project,
    ProjectPermission,
)
from users.choices import OrganizationRole
from users.constants import (
    DELETED_USER_NAME,
    INVITATION_TOKEN_BYTES,
    MAX_BULK_INVITE_ROWS,
    MAX_PENDING_INVITATIONS_PER_ORG,
)
from users.models import Invitation
from users.tasks import send_invitation_email_task
from users.two_factor import clear_two_factor

User = get_user_model()

USER_EXISTS_MESSAGE = "A user with this email already exists."
EMAIL_IN_USE_MESSAGE = "This email address is already in use."
NO_LONGER_ADMIN_MESSAGE = "You're no longer an admin of this organization."
LAST_ADMIN_LEAVING_MESSAGE = (
    "You're this organization's only admin. Make someone else an admin first, "
    "or delete the organization."
)
INVITATION_PENDING_MESSAGE = "This email already has a pending invitation."


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


def _generate_invitation_token():
    return secrets.token_urlsafe(INVITATION_TOKEN_BYTES)


def create_invitation(*, organization, invited_by, email):
    """Create a pending Invitation with a freshly generated token, recorded as
    sent by ``invited_by``. Shared by the single-invite endpoint and the bulk
    upload so both produce identical rows."""
    with transaction.atomic():
        invitation = Invitation.objects.create(
            organization=organization,
            invited_by=invited_by,
            email=email,
            token=_generate_invitation_token(),
        )
        AuditEvent.objects.record(
            invited_by, AuditVerb.INVITATION_SENT, email=invitation.email
        )
    return invitation


def find_invitation_conflict(organization, email, *, renewing=None):
    """Why ``email`` can't be sent an invitation to ``organization`` - they
    already have an account, or a working invitation is already waiting for
    them - or ``None`` if it can. ``renewing`` is the invitation being resent,
    which doesn't count against itself."""
    if User.objects.holding_email().filter(email=email).exists():
        return USER_EXISTS_MESSAGE

    pending = Invitation.objects.for_organization(organization).pending()
    if renewing:
        pending = pending.exclude(pk=renewing.pk)
    if pending.filter(email=email).exists():
        return INVITATION_PENDING_MESSAGE
    return None


def is_email_in_use(email):
    """Whether an account may not move to ``email``: someone holds it, or an
    invitation to it is waiting - an address is never both an account and a
    live invitation."""
    return (
        User.objects.holding_email().filter(email=email).exists()
        or Invitation.objects.pending().filter(email=email).exists()
    )


def refresh_invitation(invitation):
    """Give a pending invitation a new token and restart its expiry window.
    The previous link stops working, so only the latest email is usable."""
    invitation.token = _generate_invitation_token()
    invitation.sent_at = timezone.now()
    invitation.save(update_fields=["token", "sent_at", "modified"])


def blacklist_outstanding_tokens(user):
    """Revoke every refresh token issued to ``user`` - after a password
    change or reset, no session started with the old password survives."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


def bulk_create_invitations(emails, *, organization, invited_by):
    """Create a pending Invitation for each usable email. Rows that are malformed,
    over-long, duplicated in the file, already a user or a pending invite in the
    org, or past the org's pending-invitation cap are skipped and reported rather
    than failing the batch."""
    max_email_length = Invitation._meta.get_field("email").max_length
    candidate_emails = {raw.strip().lower() for raw in emails}

    existing_user_emails = {
        stored.lower()
        for stored in User.objects.holding_email()
        .filter(email__in=candidate_emails)
        .values_list("email", flat=True)
    }

    pending_invites = Invitation.objects.for_organization(organization).pending()
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
                {"email": original_email, "reason": "user already exists"}
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


def lock_organization_for_admin_change(admin):
    """Locks the admin's organization until the transaction ends, so role
    changes and deactivations in it happen one at a time, then checks that
    ``admin`` is still an active admin. Otherwise two admins demoting or
    deactivating each other at once would both succeed - neither acts on
    themselves - and leave the organization with no admin at all."""
    type(admin.organization).objects.select_for_update().get(pk=admin.organization_id)
    still_admin = User.objects.filter(
        pk=admin.pk, is_active=True, org_role=OrganizationRole.ADMIN
    ).exists()
    if not still_admin:
        raise PermissionDenied(NO_LONGER_ADMIN_MESSAGE)


def sole_owner_message(projects, documents):
    return (
        f"You're the only Owner of {projects} project(s) and {documents} "
        "document(s). Make someone else an Owner of each first, so they aren't "
        "left without anyone who can manage them."
    )


def _ensure_may_leave(user):
    """Refuses to let the organization's last active admin, or the only
    active Owner of anything, delete their account."""
    if user.org_role == OrganizationRole.ADMIN:
        other_admins = User.objects.filter(
            organization_id=user.organization_id,
            org_role=OrganizationRole.ADMIN,
            is_active=True,
        ).exclude(pk=user.pk)
        if not other_admins.exists():
            raise DRFValidationError({"detail": LAST_ADMIN_LEAVING_MESSAGE})

    projects = (
        Project.objects.for_organization(user.organization)
        .solely_owned_by(user)
        .count()
    )
    documents = (
        Document.objects.for_organization(user.organization)
        .solely_owned_by(user)
        .count()
    )
    if projects or documents:
        raise DRFValidationError({"detail": sole_owner_message(projects, documents)})


def delete_account(user):
    """Deletes ``user``'s own account by anonymising it: the row stays, so
    what they wrote keeps an author, but without their name, email address
    or password, and it can never sign in or be reactivated. Their access,
    pending requests, notifications and sessions go with it, and the address
    is free for someone else. So does their two-factor key.

    Refused for the organization's last active admin and for the only active
    Owner of anything, checked under a lock on the organization so two
    people leaving at once can't both pass - unless the organization has been
    deleted, when nobody can use what they'd leave behind anyway, and leaving
    is how they free their address before it's purged."""
    with transaction.atomic():
        organization = (
            type(user.organization)
            .objects.select_for_update()
            .get(pk=user.organization_id)
        )
        if not organization.deletion_requested_at:
            _ensure_may_leave(user)

        ProjectPermission.objects.filter(user=user).delete()
        DocumentPermission.objects.filter(user=user).delete()
        DocumentAccessRequest.objects.filter(
            requested_by=user, status=AccessRequestStatus.PENDING
        ).delete()
        Notification.objects.filter(recipient=user).delete()
        clear_two_factor(user)
        blacklist_outstanding_tokens(user)
        AuditEvent.objects.record(user, AuditVerb.ACCOUNT_DELETED)

        user.email = f"deleted-{user.pk}@deleted.invalid"
        user.name = DELETED_USER_NAME
        user.set_unusable_password()
        user.is_active = False
        user.deleted_at = timezone.now()
        user.save(
            update_fields=["email", "name", "password", "is_active", "deleted_at"]
        )
