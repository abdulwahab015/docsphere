import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'

import { HTTP_STATUS } from '@/api/constants'
import { getErrorStatus } from '@/api/errors'
import { handleSessionError } from '@/features/auth/session'

const DEFAULT_STALE_TIME_MS = 30_000
const MAX_QUERY_RETRIES = 2

/** Retries only failures that might succeed next time (network errors and
 * 5xx). A 4xx is the server's answer, and asking again won't change it. */
function shouldRetry(failureCount: number, error: unknown) {
  const status = getErrorStatus(error)
  if (status && status < HTTP_STATUS.serverError) {
    return false
  }
  return failureCount < MAX_QUERY_RETRIES
}

export function createQueryClient() {
  const queryClient: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError: (error) => handleSessionError(queryClient, error) }),
    mutationCache: new MutationCache({
      onError: (error) => handleSessionError(queryClient, error),
    }),
    defaultOptions: {
      queries: { staleTime: DEFAULT_STALE_TIME_MS, retry: shouldRetry },
    },
  })
  return queryClient
}
