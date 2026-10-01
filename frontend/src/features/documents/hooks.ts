import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { Document, DocumentUpdatePayload } from '@/api/types'
import {
  createDocument,
  deleteDocument,
  type DocumentListParams,
  fetchDocument,
  listDocuments,
  listDocumentTrash,
  restoreDocument,
  updateDocument,
} from '@/features/documents/api'
import { documentKeys } from '@/features/documents/query-keys'

export function useDocuments(params: DocumentListParams) {
  return useQuery({
    queryKey: documentKeys.list(params),
    queryFn: () => listDocuments(params),
    placeholderData: keepPreviousData,
  })
}

export function useDocument(documentId: number) {
  return useQuery({
    queryKey: documentKeys.detail(documentId),
    queryFn: () => fetchDocument(documentId),
  })
}

export function useDocumentTrash(page: number) {
  return useQuery({
    queryKey: documentKeys.trash(page),
    queryFn: () => listDocumentTrash({ page }),
    placeholderData: keepPreviousData,
  })
}

/** Caches a document the API just returned, and marks every list stale. */
function useStoreDocument() {
  const queryClient = useQueryClient()
  return (document: Document) => {
    queryClient.setQueryData(documentKeys.detail(document.id), document)
    void queryClient.invalidateQueries({ queryKey: documentKeys.lists() })
  }
}

export function useCreateDocument() {
  const storeDocument = useStoreDocument()
  return useMutation({ mutationFn: createDocument, onSuccess: storeDocument })
}

export function useUpdateDocument(documentId: number) {
  const storeDocument = useStoreDocument()
  return useMutation({
    mutationFn: (payload: DocumentUpdatePayload) => updateDocument(documentId, payload),
    onSuccess: storeDocument,
  })
}

export function useDeleteDocument(documentId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => deleteDocument(documentId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: documentKeys.detail(documentId) })
      void queryClient.invalidateQueries({ queryKey: documentKeys.all })
    },
  })
}

export function useRestoreDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: restoreDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentKeys.all }),
  })
}
