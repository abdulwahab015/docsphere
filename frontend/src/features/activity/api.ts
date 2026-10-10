import { apiClient } from '@/api/client'
import type { AuditEvent, AuditKind, Paginated } from '@/api/types'
import { startOfDay, startOfNextDay } from '@/features/activity/dates'

/** The activity list's view: page and search like any list, plus a kind and
 * a range of days (`YYYY-MM-DD`, empty for no limit). */
export interface ActivityParams {
  page: number
  search: string
  kind: AuditKind | ''
  from: string
  to: string
}

export async function listActivity({ page, search, kind, from, to }: ActivityParams) {
  const { data } = await apiClient.get<Paginated<AuditEvent>>('/audit/events/', {
    params: {
      page,
      search: search || undefined,
      kind: kind || undefined,
      after: from ? startOfDay(from) : undefined,
      before: to ? startOfNextDay(to) : undefined,
    },
  })
  return data
}
