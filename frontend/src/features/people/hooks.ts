import { keepPreviousData, useQuery } from '@tanstack/react-query'

import type { ListParams } from '@/api/types'
import { listPeople } from '@/features/people/api'
import { peopleKeys } from '@/features/people/query-keys'

export function usePeople(params: ListParams) {
  return useQuery({
    queryKey: peopleKeys.list(params),
    queryFn: () => listPeople(params),
    // Keep the current page on screen while the next one loads.
    placeholderData: keepPreviousData,
  })
}

/** The first page of people whose email matches `search`; nothing is fetched
 * until something is typed. */
export function usePeopleSearch(search: string) {
  const params: ListParams = { page: 1, search }
  return useQuery({
    queryKey: peopleKeys.list(params),
    queryFn: () => listPeople(params),
    enabled: Boolean(search),
  })
}
