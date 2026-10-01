import { defineConfig, devices } from '@playwright/test'

// Ports distinct from the dev servers (:3000 / :8000), so an end-to-end run
// never talks to - or is confused by - a local dev session.
const API_PORT = 8001
const APP_PORT = 3100
const APP_ORIGIN = `http://localhost:${APP_PORT}`
const isCI = Boolean(process.env.CI)

export default defineConfig({
  testDir: './e2e',
  // One worker: the tests share one seeded database.
  workers: 1,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  reporter: isCI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: APP_ORIGIN,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      name: 'api',
      // Fresh database, migrated and seeded from e2e/seed.json, then the real API.
      command: `make -C .. e2e-api E2E_API_PORT=${API_PORT} E2E_APP_ORIGIN=${APP_ORIGIN}`,
      url: `http://localhost:${API_PORT}/healthz/`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      name: 'app',
      // The production build, served as it will be deployed.
      command: `npm run build && npx vite preview --port ${APP_PORT} --strictPort`,
      url: APP_ORIGIN,
      env: { ...process.env, VITE_API_BASE_URL: `http://localhost:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
})
