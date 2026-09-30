import { http, HttpResponse } from 'msw'

import { apiClient } from '@/api/client'
import { createQueryClient } from '@/app/query-client'
import { authKeys } from '@/features/auth/query-keys'
import { buildCurrentUser } from '@/test/factories'
import { apiUrl, server, spyResolver } from '@/test/server'

const PROBE_PATH = '/probe/'

function probeAnswering(response: () => Response) {
  const probe = spyResolver(response)
  server.use(http.get(apiUrl(PROBE_PATH), probe))
  return probe
}

function fetchProbe(queryClient = createQueryClient()) {
  return queryClient
    .fetchQuery({ queryKey: ['probe'], queryFn: () => apiClient.get(PROBE_PATH), retryDelay: 0 })
    .catch(() => undefined)
}

describe('createQueryClient', () => {
  it('keeps query results fresh for 30 seconds by default', () => {
    const queryClient = createQueryClient()

    expect(queryClient.getDefaultOptions().queries?.staleTime).toBe(30_000)
  })

  it('retries a server error twice', async () => {
    const probe = probeAnswering(() => HttpResponse.json({}, { status: 503 }))

    await fetchProbe()

    expect(probe).toHaveBeenCalledTimes(3)
  })

  it('retries when the server is unreachable', async () => {
    const probe = probeAnswering(() => HttpResponse.error())

    await fetchProbe()

    expect(probe).toHaveBeenCalledTimes(3)
  })

  it("doesn't retry a client error", async () => {
    const probe = probeAnswering(() => HttpResponse.json({}, { status: 404 }))

    await fetchProbe()

    expect(probe).toHaveBeenCalledTimes(1)
  })

  it('routes query errors through the session handler', async () => {
    const queryClient = createQueryClient()
    queryClient.setQueryData(authKeys.currentUser, buildCurrentUser())
    probeAnswering(() => HttpResponse.json({}, { status: 402 }))

    await fetchProbe(queryClient)

    expect(queryClient.getQueryState(authKeys.currentUser)?.isInvalidated).toBe(true)
  })

  it('routes mutation errors through the session handler', async () => {
    const queryClient = createQueryClient()
    queryClient.setQueryData(authKeys.currentUser, buildCurrentUser())
    probeAnswering(() => HttpResponse.json({}, { status: 402 }))

    await queryClient
      .getMutationCache()
      .build(queryClient, { mutationFn: () => apiClient.get(PROBE_PATH) })
      .execute(undefined)
      .catch(() => undefined)

    expect(queryClient.getQueryState(authKeys.currentUser)?.isInvalidated).toBe(true)
  })
})
