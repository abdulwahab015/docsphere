import { z } from 'zod'

// Fixed when the app is built. Settings that differ between environments
// running the same build are in lib/runtime-config.ts.
export const envSchema = z.object({
  // The API's origin only (scheme + host + port), or empty when the API is
  // served from the app's own origin - production, where nginx forwards /api/
  // to Django. In development use the same hostname as the app (localhost,
  // not 127.0.0.1) so the refresh cookie counts as same-site.
  VITE_API_BASE_URL: z.union([z.url(), z.literal('')]),
  // Which version an error happened in: the git commit a release was built
  // from (lib/error-tracking.ts).
  VITE_SENTRY_RELEASE: z.string().optional(),
})

export const env = envSchema.parse(import.meta.env)
