import { envSchema } from '@/lib/env'

describe('envSchema', () => {
  it("accepts the API's origin", () => {
    expect(envSchema.parse({ VITE_API_BASE_URL: 'http://localhost:8000' })).toMatchObject({
      VITE_API_BASE_URL: 'http://localhost:8000',
    })
  })

  it("accepts an empty value, meaning the API shares the app's origin", () => {
    expect(envSchema.parse({ VITE_API_BASE_URL: '' })).toMatchObject({ VITE_API_BASE_URL: '' })
  })

  it('refuses a missing or malformed value, so a bad build fails at startup', () => {
    expect(envSchema.safeParse({}).success).toBe(false)
    expect(envSchema.safeParse({ VITE_API_BASE_URL: 'the API' }).success).toBe(false)
  })

  it('takes the release a build reports errors under, when given', () => {
    expect(envSchema.parse({ VITE_API_BASE_URL: '' })).toEqual({ VITE_API_BASE_URL: '' })
    expect(envSchema.parse({ VITE_API_BASE_URL: '', VITE_SENTRY_RELEASE: 'abc123' })).toMatchObject(
      { VITE_SENTRY_RELEASE: 'abc123' },
    )
  })
})
