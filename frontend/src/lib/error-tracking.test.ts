import { type BrowserOptions, createTransport } from '@sentry/react'

import { buildCurrentUser } from '@/test/factories'

const DSN = 'https://public@errors.example.com/1'

/** A transport that keeps what would have been sent, as text. */
function captureReports() {
  const sent: string[] = []
  const transport: BrowserOptions['transport'] = (options) =>
    createTransport(options, async (request) => {
      sent.push(
        typeof request.body === 'string' ? request.body : new TextDecoder().decode(request.body),
      )
      return {}
    })
  return { sent, transport }
}

/** A fresh copy of the module, so each test starts with tracking off. */
async function loadErrorTracking() {
  vi.resetModules()
  return import('@/lib/error-tracking')
}

describe('errorTracking', () => {
  afterEach(() => {
    window.history.replaceState(null, '', '/')
  })

  it('reports an error with the page and the user by id only', async () => {
    const { errorTracking } = await loadErrorTracking()
    const { sent, transport } = captureReports()
    window.history.replaceState(null, '', '/documents?search=private-plans')

    errorTracking.start({ dsn: DSN, environment: 'test', transport })
    errorTracking.identify(buildCurrentUser({ id: 7, email: 'ada@example.com' }))
    errorTracking.report(new Error('Something broke'))

    await vi.waitFor(() => expect(sent).toHaveLength(1))
    const [report] = sent
    expect(report).toContain('Something broke')
    expect(report).toContain('"user":{"id":"7"}')
    expect(report).toContain('"organization_id":"1"')
    expect(report).toContain('/documents')
    expect(report).not.toContain('private-plans')
    expect(report).not.toContain('ada@example.com')
  })

  it('reports nothing, and loads nothing, without a DSN', async () => {
    const { errorTracking } = await loadErrorTracking()
    const { sent, transport } = captureReports()

    errorTracking.start({ dsn: '', transport })
    errorTracking.identify(buildCurrentUser())
    errorTracking.report(new Error('Something broke'))
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(sent).toEqual([])
  })
})

describe('scrubbing', () => {
  it('keeps only the address without its query, and the user id', async () => {
    const { scrubEvent } = await loadErrorTracking()

    expect(
      scrubEvent({
        type: undefined,
        request: {
          url: 'https://docsphere.example.com/documents?search=secret',
          headers: { 'User-Agent': 'Firefox' },
        },
        user: { id: '7', email: 'ada@example.com', ip_address: '203.0.113.7' },
      }),
    ).toEqual({
      type: undefined,
      request: { url: 'https://docsphere.example.com/documents' },
      user: { id: '7' },
    })
    expect(scrubEvent({ type: undefined, user: { email: 'ada@example.com' } }).user).toEqual({})
  })

  it('drops console messages and the queries in request and page addresses', async () => {
    const { scrubBreadcrumb } = await loadErrorTracking()

    expect(scrubBreadcrumb({ category: 'console', message: 'Saving "Plans"' })).toBeNull()
    expect(
      scrubBreadcrumb({
        category: 'xhr',
        data: { url: '/api/v1/documents/?search=secret', method: 'GET', status_code: 200 },
      }),
    ).toEqual({
      category: 'xhr',
      data: { url: '/api/v1/documents/', method: 'GET', status_code: 200 },
    })
    expect(
      scrubBreadcrumb({
        category: 'navigation',
        data: { from: '/documents?search=a', to: '/documents/3' },
      }),
    ).toEqual({ category: 'navigation', data: { from: '/documents', to: '/documents/3' } })
    expect(scrubBreadcrumb({ category: 'ui.click', message: 'button' })).toEqual({
      category: 'ui.click',
      message: 'button',
    })
  })
})
