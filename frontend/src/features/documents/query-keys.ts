import type { DocumentListParams } from '@/features/documents/api'

export const documentKeys = {
  all: ['documents'] as const,
  lists: () => [...documentKeys.all, 'list'] as const,
  list: (params: DocumentListParams) => [...documentKeys.lists(), params] as const,
  detail: (documentId: number) => [...documentKeys.all, 'detail', documentId] as const,
  trash: (page: number) => [...documentKeys.all, 'trash', page] as const,
  attachments: (documentId: number) => [...documentKeys.all, 'attachments', documentId] as const,
  attachmentList: (documentId: number, page: number) =>
    [...documentKeys.attachments(documentId), page] as const,
  versions: (documentId: number) => [...documentKeys.all, 'versions', documentId] as const,
  versionList: (documentId: number, page: number) =>
    [...documentKeys.versions(documentId), 'list', page] as const,
  version: (documentId: number, revision: number) =>
    [...documentKeys.versions(documentId), 'detail', revision] as const,
}
