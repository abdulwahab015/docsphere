import { GlobeIcon, LockIcon } from 'lucide-react'

import type { AccessLevel, Visibility } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { ACCESS_LEVEL_LABELS, VISIBILITY_LABELS } from '@/lib/access'

export function VisibilityBadge({ visibility }: { visibility: Visibility }) {
  const Icon = visibility === 'PUBLIC' ? GlobeIcon : LockIcon
  return (
    <Badge variant="outline">
      <Icon aria-hidden />
      {VISIBILITY_LABELS[visibility]}
    </Badge>
  )
}

/** The signed-in user's own level on a resource; `null` means they have none
 * (e.g. an admin looking at a private project in the trash). */
export function AccessLevelBadge({ level }: { level: AccessLevel | null }) {
  return (
    <Badge variant={level === 'OWNER' ? 'default' : 'secondary'}>
      {level ? ACCESS_LEVEL_LABELS[level] : 'No access'}
    </Badge>
  )
}
