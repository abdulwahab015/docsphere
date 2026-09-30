import { http, HttpResponse } from 'msw'

import { getAccessToken, refreshAccessToken } from '@/api/access-token'
import { REFRESH_PATH } from '@/api/constants'
import { buildTokenPair } from '@/test/factories'
import { apiUrl, server, spyResolver } from '@/test/server'

function countRefreshes() {
  const refresh = spyResolver(() => HttpResponse.json(buildTokenPair()))
  server.use(http.post(apiUrl(REFRESH_PATH), refresh))
  return refresh
}

describe('refreshAccessToken', () => {
  it('stores the new access token', async () => {
    countRefreshes()

    await expect(refreshAccessToken()).resolves.toBe('new-access-token')

    expect(getAccessToken()).toBe('new-access-token')
  })

  it('shares one request between concurrent callers', async () => {
    const refresh = countRefreshes()

    await Promise.all([refreshAccessToken(), refreshAccessToken(), refreshAccessToken()])

    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('sends a new request once the previous one has finished', async () => {
    const refresh = countRefreshes()

    await refreshAccessToken()
    await refreshAccessToken()

    expect(refresh).toHaveBeenCalledTimes(2)
  })

  it('holds a cross-tab lock while refreshing when the browser supports it', async () => {
    countRefreshes()
    const request = vi.fn<(lockName: string, callback: () => Promise<string>) => Promise<string>>(
      (_lockName, callback) => callback(),
    )
    Object.defineProperty(navigator, 'locks', { value: { request }, configurable: true })

    try {
      await refreshAccessToken()
    } finally {
      Reflect.deleteProperty(navigator, 'locks')
    }

    expect(request).toHaveBeenCalledWith('docsphere-token-refresh', expect.any(Function))
  })

  it('rejects and keeps no token when the refresh cookie is rejected', async () => {
    server.use(
      http.post(apiUrl(REFRESH_PATH), () =>
        HttpResponse.json({ detail: 'Token is blacklisted' }, { status: 401 }),
      ),
    )

    await expect(refreshAccessToken()).rejects.toMatchObject({ response: { status: 401 } })

    expect(getAccessToken()).toBeNull()
  })
})
