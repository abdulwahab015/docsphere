import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import type { CurrentUser, OrganizationSummary, TokenPair } from '@/api/types'
import {
  acceptInvitation,
  confirmPasswordReset,
  login,
  logout,
  requestPasswordReset,
  signupOrganization,
} from '@/features/auth/api'
import { authKeys } from '@/features/auth/query-keys'
import { clearSession, loadSession, resyncSession, startSession } from '@/features/auth/session'
import { announceSessionChange, onSessionChangeElsewhere } from '@/features/auth/session-broadcast'

export function useCurrentUser() {
  return useQuery({ queryKey: authKeys.currentUser, queryFn: loadSession })
}

/** The signed-in user, for components rendered inside `RequireAuth`. */
export function useSignedInUser() {
  const { data: user } = useCurrentUser()
  if (!user) {
    throw new Error('useSignedInUser must be used inside RequireAuth.')
  }
  return user
}

type OrganizationMember = CurrentUser & { organization: OrganizationSummary }

/** The signed-in user with their organization, for components rendered inside
 * `RequireActiveSubscription` (which turns away accounts without one). */
export function useSignedInMember(): OrganizationMember {
  const user = useSignedInUser()
  const { organization } = user
  if (!organization) {
    throw new Error('useSignedInMember must be used inside RequireActiveSubscription.')
  }
  return { ...user, organization }
}

function useSessionStartingMutation<TPayload>(
  obtainTokens: (payload: TPayload) => Promise<TokenPair>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: TPayload) => startSession(queryClient, await obtainTokens(payload)),
    onSuccess: announceSessionChange,
  })
}

export function useLogin() {
  return useSessionStartingMutation(login)
}

export function useSignup() {
  return useSessionStartingMutation(signupOrganization)
}

export function useAcceptInvitation() {
  return useSessionStartingMutation(acceptInvitation)
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: logout,
    // Signed out locally even if the server call fails: the cookie may already
    // be gone, and the user asked to leave either way.
    onSettled: () => {
      clearSession(queryClient)
      announceSessionChange()
    },
  })
}

export function useRequestPasswordReset() {
  return useMutation({ mutationFn: requestPasswordReset })
}

export function useConfirmPasswordReset() {
  // The backend revokes every session of that user on a reset, so tabs
  // signed in as them should find out now rather than on their next refresh.
  return useMutation({ mutationFn: confirmPasswordReset, onSuccess: announceSessionChange })
}

/** Keeps this tab's session in step with sign-ins and sign-outs in other tabs. */
export function useSessionSyncAcrossTabs() {
  const queryClient = useQueryClient()
  useEffect(() => onSessionChangeElsewhere(() => resyncSession(queryClient)), [queryClient])
}
