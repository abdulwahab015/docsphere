import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { ListParams, OrgRole } from '@/api/types'
import { peopleKeys } from '@/features/people/query-keys'
import {
  bulkInvite,
  changeRole,
  createInvitation,
  deactivateUser,
  listDeactivatedUsers,
  listInvitations,
  reactivateUser,
  resendInvitation,
  revokeInvitation,
} from '@/features/team/api'
import { teamKeys } from '@/features/team/query-keys'

export function useInvitations(page: number) {
  return useQuery({
    queryKey: teamKeys.invitationsPage(page),
    queryFn: () => listInvitations(page),
    placeholderData: keepPreviousData,
  })
}

export function useDeactivatedUsers(params: ListParams) {
  return useQuery({
    queryKey: teamKeys.deactivatedList(params),
    queryFn: () => listDeactivatedUsers(params),
    placeholderData: keepPreviousData,
  })
}

/** Marks the invitation lists stale after an invitation is sent or changed. */
function useInvitationMutation<TVariables, TData>(
  mutationFn: (variables: TVariables) => Promise<TData>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: teamKeys.invitations() }),
  })
}

export function useCreateInvitation() {
  return useInvitationMutation(createInvitation)
}

export function useBulkInvite() {
  return useInvitationMutation(bulkInvite)
}

export function useResendInvitation() {
  return useInvitationMutation(resendInvitation)
}

export function useRevokeInvitation() {
  return useInvitationMutation(revokeInvitation)
}

/** Marks the member and deactivated lists stale after a change to who's in
 * the organization, or in what role. */
function useMembershipMutation<TVariables, TData>(
  mutationFn: (variables: TVariables) => Promise<TData>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: peopleKeys.all })
      void queryClient.invalidateQueries({ queryKey: teamKeys.deactivated() })
    },
  })
}

export function useChangeRole() {
  return useMembershipMutation(({ userId, orgRole }: { userId: number; orgRole: OrgRole }) =>
    changeRole(userId, orgRole),
  )
}

export function useDeactivateUser() {
  return useMembershipMutation(deactivateUser)
}

export function useReactivateUser() {
  return useMembershipMutation(reactivateUser)
}
