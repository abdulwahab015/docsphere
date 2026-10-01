import type { AccessLevel, Visibility } from '@/api/types'

/** What each access level may do - the same table as the backend's
 * `projects/mappings.py::ALLOWED_ACTIONS` (Owner > Editor > Viewer). */
export type Action = 'READ' | 'WRITE' | 'DELETE' | 'RESHARE'

const ALLOWED_ACTIONS: Record<AccessLevel, ReadonlySet<Action>> = {
  VIEWER: new Set(['READ']),
  EDITOR: new Set(['READ', 'WRITE']),
  OWNER: new Set(['READ', 'WRITE', 'DELETE', 'RESHARE']),
}

/** Whether `level` (the API's `access_level`, `null` when none) allows
 * `action`. Only decides which controls to show - the API enforces the same
 * rules on every request. */
export function can(level: AccessLevel | null, action: Action) {
  return Boolean(level && ALLOWED_ACTIONS[level].has(action))
}

export const ACCESS_LEVEL_LABELS: Record<AccessLevel, string> = {
  VIEWER: 'Viewer',
  EDITOR: 'Editor',
  OWNER: 'Owner',
}

export const VISIBILITY_LABELS: Record<Visibility, string> = {
  PRIVATE: 'Private',
  PUBLIC: 'Public',
}

/** What each visibility means, worded for the signed-in user's organization.
 * Projects and documents follow the same rule. */
export function visibilityDescriptions(organizationName: string): Record<Visibility, string> {
  return {
    PRIVATE: 'Only people you share it with can see it.',
    PUBLIC: `Everyone in ${organizationName} can view it.`,
  }
}
