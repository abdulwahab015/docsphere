import type { ListParams } from '@/api/types'

export const peopleKeys = {
  all: ['people'] as const,
  list: (params: ListParams) => [...peopleKeys.all, 'list', params] as const,
}
