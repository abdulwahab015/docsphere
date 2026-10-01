import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { AccessLevel, AccessRequest, Grant, Paginated, SharePayload } from '@/api/types'
import { useSignedInMember } from '@/features/auth/hooks'
import { documentKeys } from '@/features/documents/query-keys'
import { projectKeys } from '@/features/projects/query-keys'
import { can } from '@/lib/access'
import {
  type AccessRequestDecision,
  listGrants,
  listIncomingAccessRequests,
  listMyAccessRequests,
  type MyAccessRequestParams,
  requestEditAccess,
  reviewAccessRequest,
  revokeAccess,
  shareResource,
  type SharedResource,
  type SharedResourceKind,
} from '@/features/sharing/api'
import { accessRequestKeys, sharingKeys } from '@/features/sharing/query-keys'

const RESOURCE_KEYS: Record<SharedResourceKind, readonly string[]> = {
  project: projectKeys.all,
  document: documentKeys.all,
}

export function useGrants(resource: SharedResource, page: number) {
  return useQuery({
    queryKey: sharingKeys.grantsPage(resource, page),
    queryFn: () => listGrants(resource, page),
    placeholderData: keepPreviousData,
  })
}

/**
 * Refreshes what a change to someone's access affects. The list of people
 * always; the resource itself only when the signed-in user changed their own
 * level, since their `access_level` decides what the page offers. Having given
 * up Owner, they may no longer list who has access, so the list is only marked
 * stale then - refetching it would be refused while the page catches up.
 */
function useRefreshAfterAccessChange(resource: SharedResource) {
  const queryClient = useQueryClient()
  const signedInUser = useSignedInMember()

  return (userId: number, level: AccessLevel | null) => {
    const changedOwnAccess = userId === signedInUser.id
    if (changedOwnAccess) {
      void queryClient.invalidateQueries({ queryKey: RESOURCE_KEYS[resource.kind] })
    }
    void queryClient.invalidateQueries({
      queryKey: sharingKeys.grants(resource),
      refetchType: changedOwnAccess && !can(level, 'RESHARE') ? 'none' : 'active',
    })
  }
}

export function useShareResource(resource: SharedResource) {
  const queryClient = useQueryClient()
  const refresh = useRefreshAfterAccessChange(resource)
  return useMutation({
    mutationFn: (payload: SharePayload) => shareResource(resource, payload),
    onSuccess: (grant) => {
      // Show a changed level at once, rather than the old one until the refetch lands.
      queryClient.setQueriesData<Paginated<Grant>>(
        { queryKey: sharingKeys.grants(resource) },
        (grants) =>
          grants && {
            ...grants,
            results: grants.results.map((existing) =>
              existing.user === grant.user ? grant : existing,
            ),
          },
      )
      refresh(grant.user, grant.access_level)
    },
  })
}

export function useRevokeAccess(resource: SharedResource) {
  const refresh = useRefreshAfterAccessChange(resource)
  return useMutation({
    mutationFn: (userId: number) => revokeAccess(resource, userId),
    onSuccess: (_unused, userId) => refresh(userId, null),
  })
}

export function useIncomingAccessRequests(page: number) {
  return useQuery({
    queryKey: accessRequestKeys.incoming(page),
    queryFn: () => listIncomingAccessRequests(page),
    placeholderData: keepPreviousData,
  })
}

export function useMyAccessRequests(page: number) {
  const params: MyAccessRequestParams = { page }
  return useQuery({
    queryKey: accessRequestKeys.mine(params),
    queryFn: () => listMyAccessRequests(params),
    placeholderData: keepPreviousData,
  })
}

/** The caller's most recent request for one document, or `null` if they've
 * never asked. No placeholder: another document's answer must never show. */
export function useMyLatestAccessRequest(documentId: number) {
  const params: MyAccessRequestParams = { page: 1, document: documentId }
  return useQuery({
    queryKey: accessRequestKeys.mine(params),
    queryFn: () => listMyAccessRequests(params),
    select: (requests) => requests.results[0] ?? null,
  })
}

export function useRequestEditAccess(documentId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => requestEditAccess(documentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: accessRequestKeys.all }),
  })
}

export function useReviewAccessRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      accessRequest,
      decision,
    }: {
      accessRequest: AccessRequest
      decision: AccessRequestDecision
    }) => reviewAccessRequest(accessRequest, decision),
    onSuccess: (reviewed) => {
      // Drop the answered request at once, so it can't be answered twice.
      queryClient.setQueriesData<Paginated<AccessRequest>>(
        { queryKey: accessRequestKeys.incomingLists() },
        (requests) =>
          requests && {
            ...requests,
            count: requests.count - 1,
            results: requests.results.filter((request) => request.id !== reviewed.id),
          },
      )
      void queryClient.invalidateQueries({ queryKey: accessRequestKeys.all })
      // An approval adds the requester to the document's list of people.
      void queryClient.invalidateQueries({
        queryKey: sharingKeys.grants({ kind: 'document', id: reviewed.document }),
      })
    },
  })
}
