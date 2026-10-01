import { http, HttpResponse } from 'msw'

import { getAccessToken, setAccessToken } from '@/api/access-token'
import { apiClient } from '@/api/client'
import { REFRESH_PATH } from '@/api/constants'
import { buildTokenPair } from '@/test/factories'
import { apiUrl, server, spyResolver } from '@/test/server'

const PROBE_PATH = '/probe/'

/** Answers the probe with 401 until it sees the refreshed token. */
function protectedProbe() {
  const probe = spyResolver(({ request }) =>
    request.headers.get('Authorization') === 'Bearer new-access-token'
      ? HttpResponse.json({ ok: true })
      : HttpResponse.json({ detail: 'Token is invalid or expired' }, { status: 401 }),
  )
  server.use(http.get(apiUrl(PROBE_PATH), probe))
  return probe
}

function refreshResponding(response: () => Response) {
  const refresh = spyResolver(response)
  server.use(http.post(apiUrl(REFRESH_PATH), refresh))
  return refresh
}

describe('apiClient', () => {
  it('sends the access token as a Bearer header', async () => {
    setAccessToken('current-token')
    const probe = spyResolver(({ request }) =>
      HttpResponse.json({ authorization: request.headers.get('Authorization') }),
    )
    server.use(http.get(apiUrl(PROBE_PATH), probe))

    const { data } = await apiClient.get(PROBE_PATH)

    expect(data).toEqual({ authorization: 'Bearer current-token' })
  })

  it('sends no Authorization header when signed out', async () => {
    server.use(
      http.get(apiUrl(PROBE_PATH), ({ request }) =>
        HttpResponse.json({ authorization: request.headers.get('Authorization') }),
      ),
    )

    const { data } = await apiClient.get(PROBE_PATH)

    expect(data).toEqual({ authorization: null })
  })

  it('refreshes an expired token and replays the request', async () => {
    setAccessToken('expired-token')
    const probe = protectedProbe()
    const refresh = refreshResponding(() => HttpResponse.json(buildTokenPair()))

    const { data } = await apiClient.get(PROBE_PATH)

    expect(data).toEqual({ ok: true })
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(probe).toHaveBeenCalledTimes(2)
  })

  it('gives up after one replay if the request is still unauthorized', async () => {
    setAccessToken('expired-token')
    const probe = spyResolver(() => HttpResponse.json({ detail: 'Nope' }, { status: 401 }))
    server.use(http.get(apiUrl(PROBE_PATH), probe))
    const refresh = refreshResponding(() => HttpResponse.json(buildTokenPair()))

    await expect(apiClient.get(PROBE_PATH)).rejects.toMatchObject({ response: { status: 401 } })

    expect(refresh).toHaveBeenCalledTimes(1)
    expect(probe).toHaveBeenCalledTimes(2)
  })

  it('drops the token and rethrows the 401 when the refresh fails', async () => {
    setAccessToken('expired-token')
    protectedProbe()
    refreshResponding(() => HttpResponse.json({ detail: 'Blacklisted' }, { status: 401 }))

    await expect(apiClient.get(PROBE_PATH)).rejects.toMatchObject({ response: { status: 401 } })

    expect(getAccessToken()).toBeNull()
  })

  it("doesn't refresh on a 401 to a request that carried no token", async () => {
    server.use(
      http.post(apiUrl('/users/auth/login/'), () =>
        HttpResponse.json({ detail: 'No active account' }, { status: 401 }),
      ),
    )
    const refresh = refreshResponding(() => HttpResponse.json(buildTokenPair()))

    await expect(apiClient.post('/users/auth/login/', {})).rejects.toMatchObject({
      response: { status: 401 },
    })

    expect(refresh).not.toHaveBeenCalled()
  })

  it('passes errors that never reached the API straight through', async () => {
    const failure = new TypeError('Bad request setup')
    const interceptor = apiClient.interceptors.request.use(() => {
      throw failure
    })
    const refresh = refreshResponding(() => HttpResponse.json(buildTokenPair()))

    try {
      await expect(apiClient.get(PROBE_PATH)).rejects.toBe(failure)
    } finally {
      apiClient.interceptors.request.eject(interceptor)
    }

    expect(refresh).not.toHaveBeenCalled()
  })

  it('passes other errors straight through', async () => {
    setAccessToken('current-token')
    server.use(
      http.get(apiUrl(PROBE_PATH), () => HttpResponse.json({ detail: 'No' }, { status: 403 })),
    )
    const refresh = refreshResponding(() => HttpResponse.json(buildTokenPair()))

    await expect(apiClient.get(PROBE_PATH)).rejects.toMatchObject({ response: { status: 403 } })

    expect(refresh).not.toHaveBeenCalled()
  })
})
