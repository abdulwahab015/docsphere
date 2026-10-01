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
