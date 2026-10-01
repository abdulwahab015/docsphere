import type { ComponentProps } from 'react'

import type { AccessRequestStatus } from '@/api/types'
import { Badge } from '@/components/ui/badge'

const STATUS_LABELS: Record<AccessRequestStatus, string> = {
  PENDING: 'Pending',
  APPROVED: 'Approved',
  DENIED: 'Denied',
}

const STATUS_VARIANTS: Record<AccessRequestStatus, ComponentProps<typeof Badge>['variant']> = {
  PENDING: 'secondary',
  APPROVED: 'default',
  DENIED: 'outline',
}

export function AccessRequestStatusBadge({ status }: { status: AccessRequestStatus }) {
  return <Badge variant={STATUS_VARIANTS[status]}>{STATUS_LABELS[status]}</Badge>
}
