import { apiClient } from '@/api/client'
import type { AccessRequest, Grant, Paginated, SharePayload } from '@/api/types'

/** Projects and documents are shared the same way, under their own paths. */
export type SharedResourceKind = 'project' | 'document'

export interface SharedResource {
  kind: SharedResourceKind
  id: number
}

const RESOURCE_PATHS: Record<SharedResourceKind, string> = {
  project: '/projects/',
  document: '/documents/',
}

function sharePath({ kind, id }: SharedResource) {
  return `${RESOURCE_PATHS[kind]}${id}/share/`
}

/** Everyone with an explicit grant on the resource. Owner only. */
export async function listGrants(resource: SharedResource, page: number) {
  const { data } = await apiClient.get<Paginated<Grant>>(sharePath(resource), {
    params: { page },
  })
  return data
}

/** Gives someone a level on the resource, or changes the level they have. */
export async function shareResource(resource: SharedResource, payload: SharePayload) {
  const { data } = await apiClient.post<Grant>(sharePath(resource), payload)
  return data
}

export async function revokeAccess(resource: SharedResource, userId: number) {
  await apiClient.delete(`${sharePath(resource)}${userId}/`)
}

const ACCESS_REQUESTS_PATH = '/documents/access-requests/'

export interface MyAccessRequestParams {
  page: number
  /** Only requests for this document. */
  document?: number
}

/** Pending requests on every document the caller owns. */
export async function listIncomingAccessRequests(page: number) {
  const { data } = await apiClient.get<Paginated<AccessRequest>>(
    `${ACCESS_REQUESTS_PATH}incoming/`,
    { params: { page } },
  )
  return data
}

/** The caller's own requests in every status, newest first. */
export async function listMyAccessRequests({ page, document }: MyAccessRequestParams) {
  const { data } = await apiClient.get<Paginated<AccessRequest>>(`${ACCESS_REQUESTS_PATH}mine/`, {
    params: { page, document },
  })
  return data
}

/** Asks a document's owners for Editor access. */
export async function requestEditAccess(documentId: number) {
  const { data } = await apiClient.post<AccessRequest>(
    `${RESOURCE_PATHS.document}${documentId}/access-requests/`,
  )
  return data
}

export type AccessRequestDecision = 'approve' | 'deny'

/** Approving makes the requester an Editor; denying only records the answer. */
export async function reviewAccessRequest(
  { id, document }: AccessRequest,
  decision: AccessRequestDecision,
) {
  const { data } = await apiClient.post<AccessRequest>(
    `${RESOURCE_PATHS.document}${document}/access-requests/${id}/${decision}/`,
  )
  return data
}
