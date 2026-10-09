import type { AuditEvent, AuditKind, AuditVerb } from '@/api/types'
import { ACCESS_LEVEL_LABELS, ORG_ROLE_LABELS, VISIBILITY_LABELS } from '@/lib/access'
import { displayName } from '@/lib/people'

/** The kinds the activity list can be narrowed to, in the order offered. */
export const ACTIVITY_KINDS: readonly AuditKind[] = [
  'ACCESS',
  'MEMBERSHIP',
  'TRASH',
  'ATTACHMENTS',
  'EXPORTS',
]

export const ACTIVITY_KIND_LABELS: Record<AuditKind, string> = {
  ACCESS: 'Access',
  MEMBERSHIP: 'Membership',
  TRASH: 'Deletes and restores',
  ATTACHMENTS: 'Attachments',
  EXPORTS: 'Data exports',
}

/** Who did it: a person, or - once their account is gone - nobody to name. */
export function actorName(event: AuditEvent) {
  return event.actor_email
    ? displayName({ name: event.actor_name, email: event.actor_email })
    : 'A removed account'
}

function targetName(event: AuditEvent) {
  return event.target_user_email
    ? displayName({ name: event.target_user_name, email: event.target_user_email })
    : 'a removed account'
}

/** The project or document, by name - or, when the admin couldn't open it,
 * only that it's a private one. */
function resourceName(event: AuditEvent) {
  const kind = event.resource_kind === 'PROJECT' ? 'project' : 'document'
  return event.resource_name ? `the ${kind} "${event.resource_name}"` : `a private ${kind}`
}

/** A file's name is part of what's in a document, so the API leaves it out
 * along with the document's own name. */
function attachmentName(event: AuditEvent) {
  return event.details.file_name ? `"${event.details.file_name}"` : 'a file'
}

/** A label for a detail the event's verb always carries. */
function label<TValue extends string>(labels: Record<TValue, string>, value?: TValue) {
  return value ? labels[value] : 'unknown'
}

const DESCRIPTIONS: Record<AuditVerb, (event: AuditEvent) => string> = {
  ACCESS_GRANTED: (event) =>
    `Gave ${targetName(event)} ${label(ACCESS_LEVEL_LABELS, event.details.access_level)} access to ${resourceName(event)}`,
  ACCESS_CHANGED: (event) =>
    `Changed ${targetName(event)}'s access to ${resourceName(event)} from ${label(ACCESS_LEVEL_LABELS, event.details.previous_access_level)} to ${label(ACCESS_LEVEL_LABELS, event.details.access_level)}`,
  ACCESS_REVOKED: (event) =>
    `Removed ${targetName(event)}'s ${label(ACCESS_LEVEL_LABELS, event.details.previous_access_level)} access to ${resourceName(event)}`,
  VISIBILITY_CHANGED: (event) =>
    `Made ${resourceName(event)} ${label(VISIBILITY_LABELS, event.details.visibility).toLowerCase()}`,
  ACCESS_REQUEST_APPROVED: (event) =>
    `Approved ${targetName(event)}'s request to edit ${resourceName(event)}`,
  ACCESS_REQUEST_DENIED: (event) =>
    `Denied ${targetName(event)}'s request to edit ${resourceName(event)}`,
  ROLE_CHANGED: (event) =>
    `Changed ${targetName(event)}'s role from ${label(ORG_ROLE_LABELS, event.details.previous_role)} to ${label(ORG_ROLE_LABELS, event.details.role)}`,
  MEMBER_DEACTIVATED: (event) => `Deactivated ${targetName(event)}`,
  MEMBER_REACTIVATED: (event) => `Reactivated ${targetName(event)}`,
  INVITATION_SENT: (event) => `Invited ${event.details.email}`,
  INVITATION_RESENT: (event) => `Resent the invitation to ${event.details.email}`,
  INVITATION_REVOKED: (event) => `Revoked the invitation to ${event.details.email}`,
  INVITATION_ACCEPTED: () => 'Joined from an invitation',
  ACCOUNT_DELETED: () => 'Deleted their account',
  EXPORT_REQUESTED: () => "Asked for an export of the organization's data",
  EXPORT_DOWNLOADED: () => "Downloaded an export of the organization's data",
  DELETED: (event) => `Moved ${resourceName(event)} to the trash`,
  RESTORED: (event) => `Restored ${resourceName(event)} from the trash`,
  ATTACHMENT_ADDED: (event) => `Attached ${attachmentName(event)} to ${resourceName(event)}`,
  ATTACHMENT_DELETED: (event) => `Deleted ${attachmentName(event)} from ${resourceName(event)}`,
}

/** What happened, as a sentence whose subject is the actor. */
export function describeEvent(event: AuditEvent) {
  return DESCRIPTIONS[event.verb](event)
}
