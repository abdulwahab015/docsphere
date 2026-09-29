import { z } from 'zod'

const envSchema = z.object({
  // The API's origin only (scheme + host + port). Use the same hostname as the
  // app (localhost, not 127.0.0.1) so the refresh cookie counts as same-site.
  VITE_API_BASE_URL: z.url(),
})

export const env = envSchema.parse(import.meta.env)
