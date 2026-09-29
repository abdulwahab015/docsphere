import axios from 'axios'

import { API_ROOT, REFRESH_PATH } from '@/api/constants'
import type { TokenPair } from '@/api/types'

// Held in memory only: never persisted where page scripts could read it back.
// The refresh token lives in the backend's HttpOnly cookie instead.
let accessToken: string | null = null
let pendingRefresh: Promise<string> | null = null

const REFRESH_LOCK_NAME = 'docsphere-token-refresh'

export function getAccessToken() {
  return accessToken
}

export function setAccessToken(token: string) {
  accessToken = token
}

export function clearAccessToken() {
  accessToken = null
}

async function requestNewAccessToken() {
  // A bare request, not the shared client: its 401 must not trigger another refresh.
  const response = await axios.post<TokenPair>(
    `${API_ROOT}${REFRESH_PATH}`,
    {},
    { withCredentials: true },
  )
  return response.data.access
}

async function requestWithCrossTabLock(): Promise<string> {
  if (!navigator.locks) {
    return requestNewAccessToken()
  }
  return navigator.locks.request(REFRESH_LOCK_NAME, requestNewAccessToken)
}

/**
 * Exchanges the refresh cookie for a new access token.
 *
 * The backend rotates the refresh token on every use and blacklists the old
 * one, so two refreshes racing each other would end the session. Concurrent
 * callers in this tab share one in-flight request, and the Web Locks API
 * serializes refreshes across tabs: each tab waits until the previous one has
 * finished and the rotated cookie is in place before sending its own.
 */
export function refreshAccessToken() {
  if (!pendingRefresh) {
    pendingRefresh = requestWithCrossTabLock()
      .then((token) => {
        setAccessToken(token)
        return token
      })
      .finally(() => {
        pendingRefresh = null
      })
  }
  return pendingRefresh
}
