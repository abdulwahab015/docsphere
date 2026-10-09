import { fireEvent, screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { AuditEvent } from '@/api/types'
import { buildAuditEvent, buildCurrentUser } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const ACTIVITY_URL = '/activity'
const EVENTS_PATH = '/audit/events/'
const admin = buildCurrentUser({ org_role: 'ADMIN' })

function serveEvents(events: AuditEvent[], count = events.length) {
  const spy = spyResolver(() => HttpResponse.json({ count, results: events }))
  server.use(http.get(apiUrl(EVENTS_PATH), spy))
  return spy
}

/** The query string of the latest request for the activity. */
function lastQuery(spy: ReturnType<typeof serveEvents>) {
  const { request } = spy.mock.calls.at(-1)![0]
  const query: Record<string, string> = {}
  new URL(request.url).searchParams.forEach((value, key) => {
    query[key] = value
  })
  return query
}

describe('ActivityPage', () => {
  it('lists who did what and when, newest first', async () => {
    serveEvents([
      buildAuditEvent({ id: 2 }),
      buildAuditEvent({
        id: 1,
        verb: 'MEMBER_DEACTIVATED',
        actor_email: null,
        actor_name: null,
        resource_kind: null,
        resource_name: null,
        details: {},
      }),
    ])
    renderRoute(ACTIVITY_URL, { signedInAs: admin })

    await screen.findByText('Deactivated Grace Hopper')
    const [shared, deactivated] = within(
      screen.getByRole('list', { name: 'Activity' }),
    ).getAllByRole('listitem')
    expect(shared).toHaveTextContent(
      'Gave Grace Hopper Editor access to the document "Q3 plan"Ada Lovelace ·',
    )
    expect(deactivated).toHaveTextContent('Deactivated Grace HopperA removed account ·')
    expect(screen.getByText('Showing 1–2 of 2')).toBeInTheDocument()
  })

  it('narrows the activity by kind and days, kept in the address', async () => {
    const spy = serveEvents([buildAuditEvent()])
    const { router } = renderRoute(ACTIVITY_URL, { signedInAs: admin })
    await screen.findByText(/^Ada Lovelace ·/)

    fireEvent.change(screen.getByLabelText('Kind'), { target: { value: 'TRASH' } })
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-09-01' } })
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2026-09-30' } })

    await vi.waitFor(() =>
      expect(lastQuery(spy)).toEqual({
        page: '1',
        kind: 'TRASH',
        after: new Date('2026-09-01T00:00').toISOString(),
        before: new Date('2026-10-01T00:00').toISOString(),
      }),
    )
    expect(router.state.location.search).toBe('?kind=TRASH&from=2026-09-01&to=2026-09-30')
  })

  it("reads the filters from the address, ignoring ones it doesn't know", async () => {
    const spy = serveEvents([buildAuditEvent()])
    renderRoute(`${ACTIVITY_URL}?kind=BILLING&from=yesterday&to=2026-09-30&search=grace`, {
      signedInAs: admin,
    })
    await screen.findByText(/^Ada Lovelace ·/)

    expect(lastQuery(spy)).toEqual({
      page: '1',
      search: 'grace',
      before: new Date('2026-10-01T00:00').toISOString(),
    })
    expect(screen.getByLabelText('Kind')).toHaveValue('')
  })

  it('clearing a filter drops it, and changing one returns to the first page', async () => {
    const spy = serveEvents([buildAuditEvent()], 45)
    const { router } = renderRoute(`${ACTIVITY_URL}?kind=ACCESS&page=2`, { signedInAs: admin })
    await screen.findByText(/^Ada Lovelace ·/)

    fireEvent.change(screen.getByLabelText('Kind'), { target: { value: '' } })

    await vi.waitFor(() => expect(lastQuery(spy)).toEqual({ page: '1' }))
    expect(router.state.location.search).toBe('')
  })

  it('says when nothing has happened yet, or nothing matches', async () => {
    serveEvents([])
    const { user } = renderRoute(ACTIVITY_URL, { signedInAs: admin })

    expect(await screen.findByRole('heading', { name: 'No activity yet' })).toBeInTheDocument()

    await user.type(screen.getByLabelText('Search activity'), 'nobody')

    expect(await screen.findByRole('heading', { name: 'No matching activity' })).toBeInTheDocument()
  })

  it('offers to try again when the activity fails to load', async () => {
    server.use(http.get(apiUrl(EVENTS_PATH), () => HttpResponse.json({}, { status: 500 })))
    const { user } = renderRoute(ACTIVITY_URL, { signedInAs: admin })
    const tryAgain = await screen.findByRole('button', { name: 'Try again' })

    serveEvents([buildAuditEvent()])
    await user.click(tryAgain)

    expect(await screen.findByText(/^Ada Lovelace ·/)).toBeInTheDocument()
  })

  it('is for admins only', async () => {
    renderRoute(ACTIVITY_URL, { signedInAs: buildCurrentUser({ org_role: 'MEMBER' }) })

    expect(
      await screen.findByRole('heading', { name: "You don't have access" }),
    ).toBeInTheDocument()
  })
})
