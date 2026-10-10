import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from '@/app/App'
import '@/index.css'
import { env } from '@/lib/env'
import { errorTracking } from '@/lib/error-tracking'
import { readRuntimeConfig } from '@/lib/runtime-config'

const runtimeConfig = readRuntimeConfig(document)
errorTracking.start({
  dsn: runtimeConfig.sentryDsn,
  environment: runtimeConfig.sentryEnvironment || undefined,
  release: env.VITE_SENTRY_RELEASE || undefined,
})

const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('index.html is missing the #root element')
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
