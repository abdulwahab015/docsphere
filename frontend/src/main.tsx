import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from '@/app/App'
import '@/index.css'
import { env } from '@/lib/env'
import { errorTracking } from '@/lib/error-tracking'

errorTracking.start({
  dsn: env.VITE_SENTRY_DSN,
  environment: env.VITE_SENTRY_ENVIRONMENT,
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
