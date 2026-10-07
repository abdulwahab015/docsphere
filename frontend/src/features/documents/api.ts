import { isAxiosError } from 'axios'

import { apiClient } from '@/api/client'
import { HTTP_STATUS } from '@/api/constants'
import type {
  Document,
  DocumentCreatePayload,
  DocumentUpdatePayload,
  ListParams,
  Paginated,
} from '@/api/types'

const DOCUMENTS_PATH = '/documents/'
const EDIT_CONFLICT_CODE = 'edit_conflict'

interface EditConflictBody {
  code?: string
  document?: Document
}

export interface DocumentListParams extends ListParams {
  /** Only documents filed under this project. */
  project?: number
}

function documentPath(documentId: number) {
  return `${DOCUMENTS_PATH}${documentId}/`
}

export async function listDocuments({ page, search, project }: DocumentListParams) {
  const { data } = await apiClient.get<Paginated<Document>>(DOCUMENTS_PATH, {
    params: { page, search: search || undefined, project },
  })
  return data
}

export async function fetchDocument(documentId: number) {
  const { data } = await apiClient.get<Document>(documentPath(documentId))
  return data
}

export async function createDocument(payload: DocumentCreatePayload) {
  const { data } = await apiClient.post<Document>(DOCUMENTS_PATH, payload)
  return data
}

export async function updateDocument(documentId: number, payload: DocumentUpdatePayload) {
  const { data } = await apiClient.patch<Document>(documentPath(documentId), payload)
  return data
}

/** The document as it is now, when a save was refused because it was based
 * on an older revision - someone else saved in between. Undefined for any
 * other error. */
export function editConflictDocument(error: unknown): Document | undefined {
  if (!isAxiosError<EditConflictBody>(error) || error.response?.status !== HTTP_STATUS.conflict) {
    return undefined
  }
  const body = error.response.data
  return body.code === EDIT_CONFLICT_CODE ? body.document : undefined
}

/** A soft delete: the document moves to its owner's trash. */
export async function deleteDocument(documentId: number) {
  await apiClient.delete(documentPath(documentId))
}

/** The caller's own deleted documents - the ones they may restore. */
export async function listDocumentTrash({ page }: Pick<ListParams, 'page'>) {
  const { data } = await apiClient.get<Paginated<Document>>(`${DOCUMENTS_PATH}trash/`, {
    params: { page },
  })
  return data
}

export async function restoreDocument(documentId: number) {
  const { data } = await apiClient.post<Document>(`${documentPath(documentId)}restore/`)
  return data
}
