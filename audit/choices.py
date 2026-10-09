from django.db import models


class AuditVerb(models.TextChoices):
    """What an audit event records someone doing."""

    ACCESS_GRANTED = "ACCESS_GRANTED", "Access granted"
    ACCESS_CHANGED = "ACCESS_CHANGED", "Access changed"
    ACCESS_REVOKED = "ACCESS_REVOKED", "Access removed"
    VISIBILITY_CHANGED = "VISIBILITY_CHANGED", "Visibility changed"
    ACCESS_REQUEST_APPROVED = "ACCESS_REQUEST_APPROVED", "Access request approved"
    ACCESS_REQUEST_DENIED = "ACCESS_REQUEST_DENIED", "Access request denied"
    ROLE_CHANGED = "ROLE_CHANGED", "Role changed"
    MEMBER_DEACTIVATED = "MEMBER_DEACTIVATED", "Member deactivated"
    MEMBER_REACTIVATED = "MEMBER_REACTIVATED", "Member reactivated"
    INVITATION_SENT = "INVITATION_SENT", "Invitation sent"
    INVITATION_RESENT = "INVITATION_RESENT", "Invitation resent"
    INVITATION_REVOKED = "INVITATION_REVOKED", "Invitation revoked"
    INVITATION_ACCEPTED = "INVITATION_ACCEPTED", "Invitation accepted"
    ACCOUNT_DELETED = "ACCOUNT_DELETED", "Account deleted"
    DELETED = "DELETED", "Moved to the trash"
    RESTORED = "RESTORED", "Restored"
    ATTACHMENT_ADDED = "ATTACHMENT_ADDED", "File attached"
    ATTACHMENT_DELETED = "ATTACHMENT_DELETED", "File deleted"


class AuditKind(models.TextChoices):
    """The groups of verbs the activity list can be narrowed to."""

    ACCESS = "ACCESS", "Access"
    MEMBERSHIP = "MEMBERSHIP", "Membership"
    TRASH = "TRASH", "Deletes and restores"
    ATTACHMENTS = "ATTACHMENTS", "Attachments"
