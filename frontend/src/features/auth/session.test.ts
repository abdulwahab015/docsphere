import { http, HttpResponse } from 'msw'

import { getAccessToken, setAccessToken } from '@/api/access-token'
import { apiClient } from '@/api/client'
import { REFRESH_PATH } from '@/api/constants'
import { authKeys } from '@/features/auth/query-keys'
import {
  clearSession,
  endSessionDeliberately,
  handleSessionError,
  loadSession,
  startSession,
  wasSignedOutDeliberately,
} from '@/features/auth/session'
import { buildCurrentUser, buildTokenPair } from '@/test/factories'
import { createTestQueryClient } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const ME_PATH = '/users/me/'
const OTHER_DATA_KEY = ['projects']

function serveCurrentUser(user = buildCurrentUser()) {
  const me = spyResolver(() => HttpResponse.json(user))
  server.use(http.get(apiUrl(ME_PATH), me))
  return me
}

function refreshFailing(status: number) {
  server.use(http.post(apiUrl(REFRESH_PATH), () => HttpResponse.json({}, { status })))
}

describe('loadSession', () => {
  it('restores the session from the refresh cookie on a fresh page load', async () => {
    server.use(http.post(apiUrl(REFRESH_PATH), () => HttpResponse.json(buildTokenPair())))
    serveCurrentUser()

    await expect(loadSession()).resolves.toEqual(buildCurrentUser())

    expect(getAccessToken()).toBe('new-access-token')
  })

  it('uses the access token already in memory without refreshing', async () => {
    setAccessToken('current-token')
    const refresh = spyResolver(() => HttpResponse.json(buildTokenPair()))
    server.use(http.post(apiUrl(REFRESH_PATH), refresh))
    serveCurrentUser()

    await expect(loadSession()).resolves.toEqual(buildCurrentUser())

    expect(refresh).not.toHaveBeenCalled()
  })

  it('resolves to null when there is no refresh cookie', async () => {
    await expect(loadSession()).resolves.toBeNull()
  })

  it('resolves to null when the refresh cookie has expired', async () => {
    refreshFailing(401)

    await expect(loadSession()).resolves.toBeNull()
  })

  it('throws when the server fails, instead of signing the user out', async () => {
    refreshFailing(503)

    await expect(loadSession()).rejects.toMatchObject({ response: { status: 503 } })
  })
})

describe('startSession', () => {
  it("stores the token, caches the user, and drops the previous user's data", async () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(OTHER_DATA_KEY, ['previous user data'])
    serveCurrentUser()

    await startSession(queryClient, buildTokenPair())

    expect(getAccessToken()).toBe('new-access-token')
    expect(queryClient.getQueryData(authKeys.currentUser)).toEqual(buildCurrentUser())
    expect(queryClient.getQueryData(OTHER_DATA_KEY)).toBeUndefined()
  })
})

describe('clearSession', () => {
  it('forgets the token, the user and their data', () => {
    const queryClient = createTestQueryClient()
    setAccessToken('current-token')
    queryClient.setQueryData(authKeys.currentUser, buildCurrentUser())
    queryClient.setQueryData(OTHER_DATA_KEY, ['data'])

    clearSession(queryClient)

    expect(getAccessToken()).toBeNull()
    expect(queryClient.getQueryData(authKeys.currentUser)).toBeNull()
    expect(queryClient.getQueryData(OTHER_DATA_KEY)).toBeUndefined()
  })
})

describe('endSessionDeliberately', () => {
  it('ends the session and remembers it was a choice, until the next sign-in', async () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(authKeys.currentUser, buildCurrentUser())

    endSessionDeliberately(queryClient)

    expect(queryClient.getQueryData(authKeys.currentUser)).toBeNull()
    expect(wasSignedOutDeliberately(queryClient)).toBe(true)

    serveCurrentUser()
    await startSession(queryClient, buildTokenPair())

    expect(wasSignedOutDeliberately(queryClient)).toBe(false)
  })

  it('is not how an expired session ends', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(authKeys.currentUser, buildCurrentUser())

    clearSession(queryClient)

    expect(wasSignedOutDeliberately(queryClient)).toBe(false)
  })
})

describe('handleSessionError', () => {
  async function errorWithStatus(status: number, body = {}) {
    server.use(http.get(apiUrl('/probe/'), () => HttpResponse.json(body, { status })))
    return apiClient.get('/probe/').catch((error: unknown) => error)
  }

  it('ends the session on a 401 while signed in', async () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(authKeys.currentUser, buildCurrentUser())

    handleSessionError(queryClient, await errorWithStatus(401))

    expect(queryClient.getQueryData(authKeys.currentUser)).toBeNull()
  })

  it('ignores a 401 while signed out, e.g. wrong login credentials', async () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(authKeys.currentUser, null)
    queryClient.setQueryData(OTHER_DATA_KEY, ['data'])

    handleSessionError(queryClient, await errorWithStatus(401))

    expect(queryClient.getQueryData(OTHER_DATA_KEY)).toEqual(['data'])
  })

  it('re-reads the session on a 402 to pick up the lapsed subscription', async () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(authKeys.currentUser, buildCurrentUser())

    handleSessionError(queryClient, await errorWithStatus(402))

    expect(queryClient.getQueryState(authKeys.currentUser)?.isInvalidated).toBe(true)
  })

  it("re-reads the session when the API says the email isn't verified", async () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(authKeys.currentUser, buildCurrentUser())

    handleSessionError(
      queryClient,
      await errorWithStatus(403, {
        detail: 'Verify your email address to continue.',
        code: 'email_unverified',
      }),
    )

    expect(queryClient.getQueryState(authKeys.currentUser)?.isInvalidated).toBe(true)
  })

  it('re-reads the session when the organization starts requiring two-factor sign-in', async () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(authKeys.currentUser, buildCurrentUser())

    handleSessionError(
      queryClient,
      await errorWithStatus(403, {
        detail: 'Your organization requires two-factor sign-in. Set it up to continue.',
        code: 'two_factor_required',
      }),
    )

    expect(queryClient.getQueryState(authKeys.currentUser)?.isInvalidated).toBe(true)
  })

  it('re-reads the session when the organization was deleted', async () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(authKeys.currentUser, buildCurrentUser())

    handleSessionError(
      queryClient,
      await errorWithStatus(403, {
        detail: 'Your organization has been deleted.',
        code: 'organization_deleted',
      }),
    )

    expect(queryClient.getQueryState(authKeys.currentUser)?.isInvalidated).toBe(true)
  })

  it('leaves the session alone for other errors', async () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(authKeys.currentUser, buildCurrentUser())

    handleSessionError(queryClient, await errorWithStatus(403))

    expect(queryClient.getQueryData(authKeys.currentUser)).toEqual(buildCurrentUser())
    expect(queryClient.getQueryState(authKeys.currentUser)?.isInvalidated).toBe(false)
  })

  it('leaves the session alone for an error that never reached the API', () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(authKeys.currentUser, buildCurrentUser())

    handleSessionError(queryClient, new Error('Rendering failed'))

    expect(queryClient.getQueryState(authKeys.currentUser)?.isInvalidated).toBe(false)
  })
})
