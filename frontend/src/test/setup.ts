import '@testing-library/jest-dom/vitest'

import { configure } from '@testing-library/react'

import { clearAccessToken } from '@/api/access-token'
import { server } from '@/test/server'

// jsdom has no matchMedia; the sidebar uses it to detect a mobile viewport.
// Every query reports "no match", i.e. a desktop-sized window.
Object.defineProperty(window, 'matchMedia', {
  configurable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }),
})

// jsdom has no ResizeObserver either; Radix uses it to position tooltips and menus.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Object.defineProperty(window, 'ResizeObserver', { configurable: true, value: ResizeObserverStub })

// findBy*/waitFor give up after this long. The 1s default is too tight once
// the suite runs in parallel (and on smaller CI runners): multi-step flows such
// as a cross-tab sign-out measured ~0.6s under load against ~0.1s alone.
// Passing tests aren't slowed - they resolve as soon as the UI is ready.
configure({ asyncUtilTimeout: 3000 })

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))

afterEach(() => {
  server.resetHandlers()
  clearAccessToken()
})

afterAll(() => server.close())
