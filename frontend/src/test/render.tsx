import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'

import { setAccessToken } from '@/api/access-token'
import type { CurrentUser } from '@/api/types'
import { createQueryClient } from '@/app/query-client'
import { routes } from '@/app/routes'
import { authKeys } from '@/features/auth/query-keys'

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

interface RenderRouteOptions {
  /** Starts the test signed in as this user; signed out when omitted. */
  signedInAs?: CurrentUser
}

/** Renders the app's real route table at `path`, guards included. */
export function renderRoute(path: string, { signedInAs }: RenderRouteOptions = {}) {
  const queryClient = createTestQueryClient()
  if (signedInAs) {
    setAccessToken(SIGNED_IN_ACCESS_TOKEN)
    queryClient.setQueryData(authKeys.currentUser, signedInAs)
  }
  const router = createMemoryRouter(routes, { initialEntries: [path] })

  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router, queryClient, user: userEvent.setup() }
}
