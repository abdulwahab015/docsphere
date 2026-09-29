import '@testing-library/jest-dom/vitest'

import { clearAccessToken } from '@/api/access-token'
import { server } from '@/test/server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))

afterEach(() => {
  server.resetHandlers()
  clearAccessToken()
})

afterAll(() => server.close())
