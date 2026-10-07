import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { externalRedirect } from '@/lib/external-redirect'
import { buildCurrentUser, buildOrganizationSummary } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server } from '@/test/server'

const PORTAL_URL = 'https://billing.stripe.com/session/test'
// Any page of the app shows it; this one needs no requests of its own.
const ANY_PAGE = '/settings/account'
const pastDue = buildOrganizationSummary({ payment_failed: true })

describe('PaymentFailedBanner', () => {
  it('tells an admin a payment failed, and opens the billing portal to fix it', async () => {
    const redirect = vi.spyOn(externalRedirect, 'to').mockImplementation(() => {})
    server.use(
      http.post(apiUrl('/subscriptions/portal/'), () =>
        HttpResponse.json({ portal_url: PORTAL_URL }),
      ),
    )
    const { user } = renderRoute(ANY_PAGE, {
      signedInAs: buildCurrentUser({ org_role: 'ADMIN', organization: pastDue }),
    })

    const banner = await screen.findByRole('alert')
    expect(banner).toHaveTextContent('Your last payment failed')
    expect(banner).toHaveTextContent('Stripe is retrying your card.')
    // Still the app, not the lapsed-subscription screen.
    expect(screen.getByRole('heading', { level: 1, name: 'Account' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Update payment details' }))

    await vi.waitFor(() => expect(redirect).toHaveBeenCalledWith(PORTAL_URL))
    redirect.mockRestore()
  })

  it("isn't shown to members, who can't fix it", async () => {
    renderRoute(ANY_PAGE, { signedInAs: buildCurrentUser({ organization: pastDue }) })

    expect(await screen.findByRole('heading', { level: 1, name: 'Account' })).toBeInTheDocument()
    expect(screen.queryByText('Your last payment failed')).not.toBeInTheDocument()
  })

  it("isn't shown while payments go through", async () => {
    renderRoute(ANY_PAGE, { signedInAs: buildCurrentUser({ org_role: 'ADMIN' }) })

    expect(await screen.findByRole('heading', { level: 1, name: 'Account' })).toBeInTheDocument()
    expect(screen.queryByText('Your last payment failed')).not.toBeInTheDocument()
  })
})
