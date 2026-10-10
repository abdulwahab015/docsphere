import { act, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { CurrentUser } from '@/api/types'
import { CONFIRMATION_POLL_MS, CONFIRMATION_TIMEOUT_MS } from '@/features/billing/hooks'
import { buildCurrentUser, buildOrganizationSummary } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const lapsedAdmin = buildCurrentUser({
  org_role: 'ADMIN',
  organization: buildOrganizationSummary({ has_active_subscription: false }),
})
const subscribedAdmin = buildCurrentUser({ org_role: 'ADMIN' })

/** Answers the session check with `lapsedAdmin` until `activate()` is called. */
function serveSession() {
  let current: CurrentUser = lapsedAdmin
  const me = spyResolver(() => HttpResponse.json(current))
  server.use(http.get(apiUrl('/users/me/'), me))
  return {
    me,
    activate: () => {
      current = subscribedAdmin
    },
  }
}

async function advance(milliseconds: number) {
  await act(() => vi.advanceTimersByTimeAsync(milliseconds))
}

describe('CheckoutSuccessPage', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('waits for Stripe to confirm the payment, then lets the admin in', async () => {
    const session = serveSession()
    const { user } = renderRoute('/billing/success/', { signedInAs: lapsedAdmin })

    expect(screen.getByRole('heading', { name: 'Confirming your payment' })).toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'Waiting for confirmation' })).toBeInTheDocument()
    await advance(CONFIRMATION_POLL_MS)
    expect(session.me).toHaveBeenCalled()
    session.activate()
    await advance(CONFIRMATION_POLL_MS)

    expect(await screen.findByRole('heading', { name: "You're subscribed" })).toBeInTheDocument()
    const callsWhenConfirmed = session.me.mock.calls.length
    await advance(CONFIRMATION_POLL_MS * 3)
    expect(session.me).toHaveBeenCalledTimes(callsWhenConfirmed)

    server.use(http.get(apiUrl('/projects/'), () => HttpResponse.json({ count: 0, results: [] })))
    await user.click(screen.getByRole('link', { name: 'Start using DocSphere' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Projects' })).toBeInTheDocument()
  })

  it('says so when confirmation takes long, and checks again on request', async () => {
    const session = serveSession()
    const { user } = renderRoute('/billing/success/', { signedInAs: lapsedAdmin })

    await advance(CONFIRMATION_TIMEOUT_MS + CONFIRMATION_POLL_MS)
    expect(
      await screen.findByRole('heading', { name: 'Still confirming your payment' }),
    ).toBeInTheDocument()
    const callsAtTimeout = session.me.mock.calls.length
    await advance(CONFIRMATION_POLL_MS * 3)
    expect(session.me).toHaveBeenCalledTimes(callsAtTimeout)

    session.activate()
    await user.click(screen.getByRole('button', { name: 'Check again' }))

    expect(await screen.findByRole('heading', { name: "You're subscribed" })).toBeInTheDocument()
  })

  it('shows an organization that is already subscribed as subscribed', () => {
    renderRoute('/billing/success/', { signedInAs: subscribedAdmin })

    expect(screen.getByRole('heading', { name: "You're subscribed" })).toBeInTheDocument()
  })
})

describe('CheckoutCancelPage', () => {
  it('says nothing was charged, and leads back to billing', () => {
    renderRoute('/billing/cancel/', { signedInAs: lapsedAdmin })

    expect(screen.getByRole('heading', { name: 'Checkout cancelled' })).toBeInTheDocument()
    expect(screen.getByText(/You haven't been charged/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to billing' })).toHaveAttribute(
      'href',
      '/billing',
    )
  })
})
