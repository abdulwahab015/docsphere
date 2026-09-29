import { createQueryClient } from '@/app/query-client'

describe('createQueryClient', () => {
  it('keeps query results fresh for 30 seconds by default', () => {
    const queryClient = createQueryClient()

    expect(queryClient.getDefaultOptions().queries?.staleTime).toBe(30_000)
  })
})
