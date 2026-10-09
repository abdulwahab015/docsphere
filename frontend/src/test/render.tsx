import { QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, type RouteObject, RouterProvider } from 'react-router'

import { clearAccessToken, setAccessToken } from '@/api/access-token'
import type { CurrentUser } from '@/api/types'
import { PATHS } from '@/app/paths'
import { createQueryClient } from '@/app/query-client'
import { routes } from '@/app/routes'
import { authKeys } from '@/features/auth/query-keys'
import { buildCurrentUser } from '@/test/factories'

export const SIGNED_IN_ACCESS_TOKEN = 'signed-in-access-token'

/** A query client configured like the app's, minus retries, so a failing
 * request fails a test immediately instead of after backoff delays. */
export function createTestQueryClient() {
  const queryClient = createQueryClient()
  queryClient.setDefaultOptions({
    queries: { ...queryClient.getDefaultOptions().queries, retry: false },
  })
  return queryClient
}

/** The route table with every lazily loaded page already loaded, so a test
 * sees its page on the first render, as a visitor whose browser already has
 * the page's code would. */
async function withPagesLoaded(routeTable: RouteObject[]): Promise<RouteObject[]> {
  return Promise.all(
    routeTable.map(async ({ lazy, children, ...route }) => {
      const page = typeof lazy === 'function' ? await lazy() : {}
      const loadedChildren = children && { children: await withPagesLoaded(children) }
      return { ...route, ...page, ...loadedChildren } as RouteObject
    }),
  )
}

const routesWithPagesLoaded = await withPagesLoaded(routes)

interface RenderRouteOptions {
  /** Starts the test signed in as this user; signed out when omitted. */
  signedInAs?: CurrentUser
  /** Loads each page's code when its route is first visited, as the app does,
   * instead of up front. */
  loadPagesOnDemand?: boolean
}

/** Renders the app's real route table at `path`, guards included. */
export function renderRoute(
  path: string,
  { signedInAs, loadPagesOnDemand = false }: RenderRouteOptions = {},
) {
  const queryClient = createTestQueryClient()
  if (signedInAs) {
    setAccessToken(SIGNED_IN_ACCESS_TOKEN)
    queryClient.setQueryData(authKeys.currentUser, signedInAs)
  }
  const router = createMemoryRouter(loadPagesOnDemand ? routes : routesWithPagesLoaded, {
    initialEntries: [path],
  })

  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router, queryClient, user: userEvent.setup() }
}

/**
 * Renders the signed-in app once before a file's tests, and throws it away.
 * Each test file runs in a fresh worker, so its first render is several times
 * slower than the rest (measured: ~2.2s against ~0.5s under the full suite's
 * load) while React, the router and the shell are first compiled and run. Paid
 * inside a test, that comes out of the test's own wait for the page, which
 * then times out whenever the machine is busy. The account page needs only
 * what the test server answers by default, so this runs before any test sets
 * up a server response.
 */
async function warmUp() {
  renderRoute(PATHS.account, { signedInAs: buildCurrentUser() })
  await screen.findByRole('heading', { name: 'Account', level: 1 })
  cleanup()
  clearAccessToken()
}

beforeAll(warmUp)
