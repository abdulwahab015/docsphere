import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useCallback } from 'react'
import { useSearchParams } from 'react-router'

import type { AuditKind } from '@/api/types'
import { type ActivityParams, listActivity } from '@/features/activity/api'
import { ACTIVITY_KINDS } from '@/features/activity/describe'
import { isDay } from '@/features/activity/dates'
import { activityKeys } from '@/features/activity/query-keys'

export type ActivityFilter = 'kind' | 'from' | 'to'

const PAGE_PARAM = 'page'

export function useActivity(params: ActivityParams) {
  return useQuery({
    queryKey: activityKeys.list(params),
    queryFn: () => listActivity(params),
    placeholderData: keepPreviousData,
  })
}

function parseKind(value: string | null): AuditKind | '' {
  return ACTIVITY_KINDS.find((kind) => kind === value) ?? ''
}

function parseDay(value: string | null) {
  return value && isDay(value) ? value : ''
}

/** The activity list's kind and days, kept in the URL beside `?page=` and
 * `?search=`; changing one starts again from the first page. */
export function useActivityFilters() {
  const [searchParams, setSearchParams] = useSearchParams()

  const setFilter = useCallback(
    (filter: ActivityFilter, value: string) =>
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current)
          next.delete(PAGE_PARAM)
          if (value) {
            next.set(filter, value)
          } else {
            next.delete(filter)
          }
          return next
        },
        { replace: true },
      ),
    [setSearchParams],
  )

  return {
    kind: parseKind(searchParams.get('kind')),
    from: parseDay(searchParams.get('from')),
    to: parseDay(searchParams.get('to')),
    setFilter,
  }
}
