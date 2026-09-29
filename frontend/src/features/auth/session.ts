import { hashKey, type QueryClient } from '@tanstack/react-query'

import {
  clearAccessToken,
  getAccessToken,
  refreshAccessToken,
  setAccessToken,
} from '@/api/access-token'
import { HTTP_STATUS } from '@/api/constants'
import { getErrorStatus } from '@/api/errors'
import type { CurrentUser, TokenPair } from '@/api/types'
import { fetchCurrentUser } from '@/features/auth/api'
import { authKeys } from '@/features/auth/query-keys'

// The refresh endpoint's answers when there is no usable session: 400 when no
// refresh cookie was sent at all, 401 when it's expired or blacklisted.
const NO_SESSION_STATUSES = new Set<number | undefined>([
  HTTP_STATUS.badRequest,
  HTTP_STATUS.unauthorized,
])

/**
 * Resolves who is signed in, or `null` when nobody is. With no access token in
 * memory (a fresh page load), it first tries to restore the session from the
 * refresh cookie. Network and server failures still throw, so they surface as
 * an error rather than as a silent sign-out.
 */
export async function loadSession(): Promise<CurrentUser | null> {
  if (!getAccessToken()) {
    try {
      await refreshAccessToken()
    } catch (error) {
      if (NO_SESSION_STATUSES.has(getErrorStatus(error))) {
        return null
      }
      throw error
    }
  }
  return fetchCurrentUser()
}

/** Drops every cached query except the session itself, so data fetched for
 * one user can never be shown to the next. */
function removeUserData(queryClient: QueryClient) {
  const sessionHash = hashKey(authKeys.currentUser)
  queryClient.removeQueries({ predicate: (query) => query.queryHash !== sessionHash })
}

export async function startSession(queryClient: QueryClient, tokens: TokenPair) {
  removeUserData(queryClient)
  setAccessToken(tokens.access)
  queryClient.setQueryData(authKeys.currentUser, await fetchCurrentUser())
}

export function clearSession(queryClient: QueryClient) {
  clearAccessToken()
  removeUserData(queryClient)
  queryClient.setQueryData(authKeys.currentUser, null)
}

/**
 * Reacts to errors from any query or mutation: a 401 that survived the
 * client's refresh attempt means the session is over; a 402 means the
 * organization's subscription lapsed, so the session is re-read to pick up
 * its new subscription state.
 */
export function handleSessionError(queryClient: QueryClient, error: unknown) {
  const status = getErrorStatus(error)
  const isSignedIn = Boolean(queryClient.getQueryData(authKeys.currentUser))

  if (status === HTTP_STATUS.unauthorized && isSignedIn) {
    clearSession(queryClient)
  } else if (status === HTTP_STATUS.paymentRequired) {
    void queryClient.invalidateQueries({ queryKey: authKeys.currentUser })
  }
}
