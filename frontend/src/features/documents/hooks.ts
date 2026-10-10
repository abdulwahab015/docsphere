import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { Attachment, Document, DocumentUpdatePayload } from '@/api/types'
import {
  createDocument,
  deleteAttachment,
  deleteDocument,
  downloadAttachment,
  type DocumentListParams,
  editConflictDocument,
  fetchDocument,
  fetchDocumentVersion,
  listAttachments,
  listDocuments,
  listDocumentVersions,
  listDocumentTrash,
  restoreDocument,
  updateDocument,
  uploadAttachment,
} from '@/features/documents/api'
import { documentKeys } from '@/features/documents/query-keys'
import { fileSaver } from '@/lib/save-file'

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

/** A document's history, newest first. Editors and Owners only. */
export function useDocumentVersions(documentId: number, page: number) {
  return useQuery({
    queryKey: documentKeys.versionList(documentId, page),
    queryFn: () => listDocumentVersions(documentId, page),
    placeholderData: keepPreviousData,
  })
}

export function useDocumentVersion(documentId: number, revision: number) {
  return useQuery({
    queryKey: documentKeys.version(documentId, revision),
    queryFn: () => fetchDocumentVersion(documentId, revision),
  })
}

export function useDocumentTrash(page: number) {
  return useQuery({
    queryKey: documentKeys.trash(page),
    queryFn: () => listDocumentTrash({ page }),
    placeholderData: keepPreviousData,
  })
}

/** Caches a document the API just returned, and marks every list - and its
 * history, which a save may have added to - stale. */
function useStoreDocument() {
  const queryClient = useQueryClient()
  return (document: Document) => {
    queryClient.setQueryData(documentKeys.detail(document.id), document)
    void queryClient.invalidateQueries({ queryKey: documentKeys.lists() })
    void queryClient.invalidateQueries({ queryKey: documentKeys.versions(document.id) })
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
    onError: (error) => {
      // Someone else saved first: show the document as it is now. An editor
      // with unsaved text keeps it, and decides what to do.
      const current = editConflictDocument(error)
      if (current) {
        storeDocument(current)
      }
    },
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

export function useAttachments(documentId: number, page: number) {
  return useQuery({
    queryKey: documentKeys.attachmentList(documentId, page),
    queryFn: () => listAttachments(documentId, page),
    placeholderData: keepPreviousData,
  })
}

/** Attaches a file. `onProgress` follows the upload from 0 to 1. */
export function useUploadAttachment(documentId: number, onProgress: (fraction: number) => void) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => uploadAttachment(documentId, file, onProgress),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: documentKeys.attachments(documentId) }),
  })
}

/** Fetches an attached file through the API, then saves it in the browser. */
export function useDownloadAttachment(documentId: number) {
  return useMutation({
    mutationFn: async (attachment: Attachment) =>
      fileSaver.save(await downloadAttachment(documentId, attachment.id), attachment.name),
  })
}

export function useDeleteAttachment(documentId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (attachment: Attachment) => deleteAttachment(documentId, attachment.id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: documentKeys.attachments(documentId) }),
  })
}
