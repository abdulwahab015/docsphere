import { z } from 'zod'

export const envSchema = z.object({
  // The API's origin only (scheme + host + port), or empty when the API is
  // served from the app's own origin - production, where nginx forwards /api/
  // to Django. In development use the same hostname as the app (localhost,
  // not 127.0.0.1) so the refresh cookie counts as same-site.
  VITE_API_BASE_URL: z.union([z.url(), z.literal('')]),
  // Error reporting (lib/error-tracking.ts): off without a DSN.
  VITE_SENTRY_DSN: z.union([z.url(), z.literal('')]).default(''),
  VITE_SENTRY_ENVIRONMENT: z.string().default('production'),
  // Which version an error happened in, e.g. the git commit it was built from.
  VITE_SENTRY_RELEASE: z.string().optional(),
})

export const env = envSchema.parse(import.meta.env)
