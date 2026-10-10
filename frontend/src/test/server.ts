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

/** A response held back until `release()` is called, so a test can look at
 * the UI while the request is still in flight. */
export function heldResponse(response: () => Response) {
  let release = () => {}
  const released = new Promise<void>((resolve) => {
    release = resolve
  })
  const resolver = async () => {
    await released
    return response()
  }
  return { resolver, release }
}

export const server = setupServer(
  // By default nobody is signed in: the browser holds no refresh cookie,
  // which the refresh endpoint answers with a 400.
  http.post(apiUrl(REFRESH_PATH), () =>
    HttpResponse.json({ refresh: ['This field may not be null.'] }, { status: 400 }),
  ),
  // Signing in lands on the projects list; by default there are none, and no
  // documents either (a project's page lists its documents).
  http.get(apiUrl('/projects/'), () => HttpResponse.json({ count: 0, results: [] })),
  http.get(apiUrl('/documents/'), () => HttpResponse.json({ count: 0, results: [] })),
  // A Viewer's document page looks up their earlier requests for edit access.
  http.get(apiUrl('/documents/access-requests/mine/'), () =>
    HttpResponse.json({ count: 0, results: [] }),
  ),
  // Every document page lists the document's files; by default it has none.
  http.get(apiUrl('/documents/:documentId/attachments/'), () =>
    HttpResponse.json({ count: 0, results: [] }),
  ),
  // The account page shows whether two-factor sign-in is on; by default it's off.
  http.get(apiUrl('/users/me/two-factor/'), () =>
    HttpResponse.json({ enabled: false, recovery_codes_left: 0 }),
  ),
  // The top bar's bell asks for unread notifications on every signed-in page.
  http.get(apiUrl('/notifications/unread-count/'), () => HttpResponse.json({ count: 0 })),
  http.get(apiUrl('/notifications/'), () => HttpResponse.json({ count: 0, results: [] })),
)
