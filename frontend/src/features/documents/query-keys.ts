import type { DocumentListParams } from '@/features/documents/api'

export const documentKeys = {
  all: ['documents'] as const,
  lists: () => [...documentKeys.all, 'list'] as const,
  list: (params: DocumentListParams) => [...documentKeys.lists(), params] as const,
  detail: (documentId: number) => [...documentKeys.all, 'detail', documentId] as const,
  trash: (page: number) => [...documentKeys.all, 'trash', page] as const,
}
