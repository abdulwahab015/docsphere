import { http, HttpResponse, type HttpResponseResolver } from 'msw'
import { setupServer } from 'msw/node'

import { API_ROOT, REFRESH_PATH } from '@/api/constants'

export function apiUrl(path: string) {
  return `${API_ROOT}${path}`
}

/** An MSW resolver that also records the requests it answers, so a test can
 * count them or read what was sent. */
export function spyResolver(resolver: HttpResponseResolver) {
  return vi.fn<HttpResponseResolver>(resolver)
}

// By default nobody is signed in: the browser holds no refresh cookie, which
// the refresh endpoint answers with a 400.
export const server = setupServer(
  http.post(apiUrl(REFRESH_PATH), () =>
    HttpResponse.json({ refresh: ['This field may not be null.'] }, { status: 400 }),
  ),
)
