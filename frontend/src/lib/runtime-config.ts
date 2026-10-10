import { z } from 'zod'

// Settings that differ between environments running the same build (staging
// and production run one image): nginx writes them into index.html's <meta>
// tags as it starts (frontend/nginx). Nothing fills them in during
// development or tests, where they stay empty.
const META_NAMES = {
  sentryDsn: 'sentry-dsn',
  sentryEnvironment: 'sentry-environment',
} as const

export const runtimeConfigSchema = z.object({
  // Error reporting (lib/error-tracking.ts): off without a DSN.
  sentryDsn: z.union([z.url(), z.literal('')]),
  sentryEnvironment: z.string(),
})

export type RuntimeConfig = z.infer<typeof runtimeConfigSchema>

/** Reads the settings from the page. A malformed one fails at startup, as a
 * bad build-time variable does. */
export function readRuntimeConfig(page: Document): RuntimeConfig {
  const read = (name: string) =>
    page.querySelector<HTMLMetaElement>(`meta[name="${name}"]`)?.content ?? ''
  return runtimeConfigSchema.parse({
    sentryDsn: read(META_NAMES.sentryDsn),
    sentryEnvironment: read(META_NAMES.sentryEnvironment),
  })
}
