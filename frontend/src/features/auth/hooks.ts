import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { TokenPair } from '@/api/types'
import {
  acceptInvitation,
  confirmPasswordReset,
  login,
  logout,
  requestPasswordReset,
  signupOrganization,
} from '@/features/auth/api'
import { authKeys } from '@/features/auth/query-keys'
import { clearSession, loadSession, startSession } from '@/features/auth/session'

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

function useSessionStartingMutation<TPayload>(
  obtainTokens: (payload: TPayload) => Promise<TokenPair>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: TPayload) => startSession(queryClient, await obtainTokens(payload)),
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
    onSettled: () => clearSession(queryClient),
  })
}

export function useRequestPasswordReset() {
  return useMutation({ mutationFn: requestPasswordReset })
}

export function useConfirmPasswordReset() {
  return useMutation({ mutationFn: confirmPasswordReset })
}
