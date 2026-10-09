import { hashKey, type QueryClient } from '@tanstack/react-query'

import {
  clearAccessToken,
  getAccessToken,
  refreshAccessToken,
  setAccessToken,
} from '@/api/access-token'
import { HTTP_STATUS } from '@/api/constants'
import { getErrorCode, getErrorStatus } from '@/api/errors'
import type { CurrentUser, TokenPair } from '@/api/types'
import { fetchCurrentUser } from '@/features/auth/api'
import { authKeys } from '@/features/auth/query-keys'

// The API's refusal to a signed-in user who hasn't verified their email yet.
const EMAIL_UNVERIFIED_CODE = 'email_unverified'
const TWO_FACTOR_REQUIRED_CODE = 'two_factor_required'
const ORGANIZATION_DELETED_CODE = 'organization_deleted'

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

/** The same user was issued a new token pair (changing a password revokes the
 * old ones), so only the access token changes and their data stays. The new
 * refresh token arrives as the cookie. */
export function renewSession(tokens: TokenPair) {
  setAccessToken(tokens.access)
}

export function clearSession(queryClient: QueryClient) {
  clearAccessToken()
  removeUserData(queryClient)
  queryClient.setQueryData(authKeys.currentUser, null)
}

/** Ends the session because the user chose to log out. Unlike an expired
 * session, this doesn't remember the page they were on: whoever signs in next
 * on this tab may be someone else. Cleared with the rest of the cached data
 * when the next session starts. */
export function endSessionDeliberately(queryClient: QueryClient) {
  clearSession(queryClient)
  queryClient.setQueryData(authKeys.deliberateSignOut, true)
}

export function wasSignedOutDeliberately(queryClient: QueryClient) {
  return Boolean(queryClient.getQueryData(authKeys.deliberateSignOut))
}

/**
 * Another tab signed in or out. The refresh cookie is shared between tabs, so
 * this tab forgets its own token and data and re-reads the session from the
 * cookie: signed out if the other tab logged out, or the new user if it signed
 * in as someone else.
 */
export function resyncSession(queryClient: QueryClient) {
  clearAccessToken()
  removeUserData(queryClient)
  void queryClient.resetQueries({ queryKey: authKeys.currentUser })
}

/**
 * Reacts to errors from any query or mutation: a 401 that survived the
 * client's refresh attempt means the session is over; a 402 means the
 * organization's subscription lapsed, a 403 `email_unverified` that the
 * account's email isn't verified, a 403 `two_factor_required` that the
 * organization now requires two-factor sign-in and a 403
 * `organization_deleted` that the organization was deleted, so the session is
 * re-read to pick up its new state.
 */
export function handleSessionError(queryClient: QueryClient, error: unknown) {
  const status = getErrorStatus(error)
  const isSignedIn = Boolean(queryClient.getQueryData(authKeys.currentUser))

  if (status === HTTP_STATUS.unauthorized && isSignedIn) {
    clearSession(queryClient)
  } else if (
    status === HTTP_STATUS.paymentRequired ||
    getErrorCode(error) === EMAIL_UNVERIFIED_CODE ||
    getErrorCode(error) === TWO_FACTOR_REQUIRED_CODE ||
    getErrorCode(error) === ORGANIZATION_DELETED_CODE
  ) {
    void queryClient.invalidateQueries({ queryKey: authKeys.currentUser })
  }
}
