import type { ListParams } from '@/api/types'

export const projectKeys = {
  all: ['projects'] as const,
  lists: () => [...projectKeys.all, 'list'] as const,
  list: (params: ListParams) => [...projectKeys.lists(), params] as const,
  detail: (projectId: number) => [...projectKeys.all, 'detail', projectId] as const,
  trash: (page: number) => [...projectKeys.all, 'trash', page] as const,
}
