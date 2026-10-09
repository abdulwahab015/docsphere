import type { Notification, NotificationVerb } from '@/api/types'
import { documentPath, PATHS, projectPath } from '@/app/paths'
import { ACCESS_LEVEL_LABELS } from '@/lib/access'
import { displayName } from '@/lib/people'

function actorName(notification: Notification) {
  return notification.actor_email
    ? displayName({ name: notification.actor_name, email: notification.actor_email })
    : 'A removed account'
}

/** The project or document by name - or, once the recipient can't open it
 * any more, only what kind it was. */
function resourceName(notification: Notification) {
  const kind = notification.resource_kind === 'PROJECT' ? 'project' : 'document'
  return notification.resource_name
    ? `"${notification.resource_name}"`
    : `a ${kind} you can no longer open`
}

function levelName(notification: Notification) {
  const level = notification.details.access_level
  return level ? ACCESS_LEVEL_LABELS[level] : 'a new level'
}

const DESCRIPTIONS: Record<NotificationVerb, (notification: Notification) => string> = {
  ACCESS_GRANTED: (notification) =>
    `${actorName(notification)} shared ${resourceName(notification)} with you as ${levelName(notification)}`,
  ACCESS_CHANGED: (notification) =>
    `${actorName(notification)} changed your access to ${resourceName(notification)} to ${levelName(notification)}`,
  ACCESS_REQUESTED: (notification) =>
    `${actorName(notification)} asked to edit ${resourceName(notification)}`,
  ACCESS_REQUEST_APPROVED: (notification) =>
    `${actorName(notification)} approved your request to edit ${resourceName(notification)}`,
  ACCESS_REQUEST_DENIED: (notification) =>
    `${actorName(notification)} denied your request to edit ${resourceName(notification)}`,
}

/** What happened, as a sentence. */
export function describeNotification(notification: Notification) {
  return DESCRIPTIONS[notification.verb](notification)
}

/** Where opening the notification goes: a request to answer goes to the
 * Requests page; anything else to the project or document, while the
 * recipient can still open it - otherwise nowhere. */
export function notificationLink(notification: Notification) {
  if (notification.verb === 'ACCESS_REQUESTED') {
    return PATHS.accessRequests
  }
  if (!notification.resource_id) {
    return null
  }
  return notification.resource_kind === 'PROJECT'
    ? projectPath(notification.resource_id)
    : documentPath(notification.resource_id)
}
