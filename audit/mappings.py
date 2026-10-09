from audit.choices import AuditKind, AuditVerb

VERBS_BY_KIND = {
    AuditKind.ACCESS: (
        AuditVerb.ACCESS_GRANTED,
        AuditVerb.ACCESS_CHANGED,
        AuditVerb.ACCESS_REVOKED,
        AuditVerb.VISIBILITY_CHANGED,
        AuditVerb.ACCESS_REQUEST_APPROVED,
        AuditVerb.ACCESS_REQUEST_DENIED,
    ),
    AuditKind.MEMBERSHIP: (
        AuditVerb.ROLE_CHANGED,
        AuditVerb.MEMBER_DEACTIVATED,
        AuditVerb.MEMBER_REACTIVATED,
        AuditVerb.INVITATION_SENT,
        AuditVerb.INVITATION_RESENT,
        AuditVerb.INVITATION_REVOKED,
        AuditVerb.INVITATION_ACCEPTED,
        AuditVerb.ACCOUNT_DELETED,
    ),
    AuditKind.TRASH: (AuditVerb.DELETED, AuditVerb.RESTORED),
    AuditKind.ATTACHMENTS: (AuditVerb.ATTACHMENT_ADDED, AuditVerb.ATTACHMENT_DELETED),
    AuditKind.EXPORTS: (AuditVerb.EXPORT_REQUESTED, AuditVerb.EXPORT_DOWNLOADED),
}

# Details that describe what's inside a project or document, withheld along
# with its name from an admin who can't open it.
RESOURCE_CONTENT_DETAILS = ("file_name",)
