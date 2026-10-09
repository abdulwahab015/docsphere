import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useContext, useEffect } from 'react'

import type { LoginPayload, TokenPair } from '@/api/types'
import {
  acceptInvitation,
  confirmEmailChange,
  confirmPasswordReset,
  login,
  loginWithTwoFactor,
  logout,
  requestPasswordReset,
  resendVerificationEmail,
  signupOrganization,
  verifyEmail,
} from '@/features/auth/api'
import { authKeys } from '@/features/auth/query-keys'
import {
  clearSession,
  endSessionDeliberately,
  loadSession,
  resyncSession,
  startSession,
} from '@/features/auth/session'
import { announceSessionChange, onSessionChangeElsewhere } from '@/features/auth/session-broadcast'
import { OrganizationMemberContext, SignedInUserContext } from '@/features/auth/session-context'

export function useCurrentUser() {
  return useQuery({ queryKey: authKeys.currentUser, queryFn: loadSession })
}

/** The signed-in user, for components rendered inside `RequireAuth`. */
export function useSignedInUser() {
  const user = useContext(SignedInUserContext)
  if (!user) {
    throw new Error('useSignedInUser must be used inside RequireAuth.')
  }
  return user
}

/** The signed-in user with their organization, for components rendered inside
 * `RequireActiveSubscription` (which turns away accounts without one). */
export function useSignedInMember() {
  const member = useContext(OrganizationMemberContext)
  if (!member) {
    throw new Error('useSignedInMember must be used inside RequireActiveSubscription.')
  }
  return member
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

/** Checks the email and password. Signs the user in - unless their account
 * has two-factor sign-in on: then nobody is signed in yet, and the result is
 * the token `useLoginWithTwoFactor` sends back with a code. */
export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: LoginPayload) => {
      const result = await login(payload)
      if ('two_factor_token' in result) {
        return result
      }
      await startSession(queryClient, result)
      return null
    },
    onSuccess: (challenge) => {
      if (!challenge) {
        announceSessionChange()
      }
    },
  })
}

/** The code step of logging in to an account with two-factor sign-in on. */
export function useLoginWithTwoFactor() {
  return useSessionStartingMutation(loginWithTwoFactor)
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
      endSessionDeliberately(queryClient)
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

/** Verifies the address from the emailed link. A tab still showing "Check
 * your email" (often not the one the link opened in) re-reads the session and
 * lets its user in. */
export function useVerifyEmail() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: verifyEmail,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: authKeys.currentUser })
      announceSessionChange()
    },
  })
}

export function useResendVerificationEmail() {
  return useMutation({ mutationFn: resendVerificationEmail })
}

/** Moves the account to the address the link was emailed to. The API signs
 * the account out everywhere, so this tab and the others drop the session
 * now rather than on their next request. */
export function useConfirmEmailChange() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: confirmEmailChange,
    onSuccess: () => {
      clearSession(queryClient)
      announceSessionChange()
    },
  })
}

/** Keeps this tab's session in step with sign-ins and sign-outs in other tabs. */
export function useSessionSyncAcrossTabs() {
  const queryClient = useQueryClient()
  useEffect(() => onSessionChangeElsewhere(() => resyncSession(queryClient)), [queryClient])
}
