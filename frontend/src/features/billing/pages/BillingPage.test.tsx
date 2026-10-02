import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { Organization } from '@/api/types'
import { externalRedirect } from '@/lib/external-redirect'
import { buildCurrentUser, buildOrganization, buildPrice } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, heldResponse, server, spyResolver } from '@/test/server'

const PROFILE_PATH = '/organizations/profile/'
const PORTAL_PATH = '/subscriptions/portal/'
const PORTAL_URL = 'https://billing.stripe.com/session/test'
const admin = buildCurrentUser({ org_role: 'ADMIN' })

function serveOrganization(organization: Organization = buildOrganization()) {
  server.use(http.get(apiUrl(PROFILE_PATH), () => HttpResponse.json(organization)))
}

function withSubscription(changes: Partial<NonNullable<Organization['active_subscription']>>) {
  const organization = buildOrganization()
  return {
    ...organization,
    active_subscription: { ...organization.active_subscription!, ...changes },
  }
}

describe('BillingPage', () => {
  let redirect: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    redirect = vi.spyOn(externalRedirect, 'to').mockImplementation(() => {})
  })

  afterEach(() => {
    redirect.mockRestore()
  })

  describe('the current plan', () => {
    it('shows the plan, when it renews, and the billing email', async () => {
      serveOrganization()
      renderRoute('/billing', { signedInAs: admin })

      expect(await screen.findByText('Yearly plan')).toBeInTheDocument()
      expect(screen.getByRole('heading', { level: 1, name: 'Billing' })).toBeInTheDocument()
      expect(screen.getByText('Active')).toBeInTheDocument()
      expect(screen.getByText(/^Renews on /)).toBeInTheDocument()
      expect(screen.getByLabelText('Billing email')).toHaveValue('billing@acme.test')
      expect(screen.queryByRole('list', { name: 'Plans' })).not.toBeInTheDocument()
    })

    it("says when the subscription won't renew", async () => {
      serveOrganization(withSubscription({ cancel_at_period_end: true }))
      renderRoute('/billing', { signedInAs: admin })

      expect(await screen.findByText(/^Ends on /)).toBeInTheDocument()
    })

    it('leaves out the date when Stripe has not reported one, and names an unknown interval as is', async () => {
      serveOrganization(withSubscription({ current_period_end: null, interval: 'fortnight' }))
      renderRoute('/billing', { signedInAs: admin })

      expect(await screen.findByText('fortnight plan')).toBeInTheDocument()
      expect(screen.queryByText(/^(Renews|Ends) on /)).not.toBeInTheDocument()
    })

    it('opens the billing portal, staying busy while the browser leaves', async () => {
      serveOrganization()
      const portal = heldResponse(() => HttpResponse.json({ portal_url: PORTAL_URL }))
      server.use(http.post(apiUrl(PORTAL_PATH), portal.resolver))
      const { user } = renderRoute('/billing', { signedInAs: admin })

      const button = await screen.findByRole('button', { name: 'Manage billing' })
      await user.click(button)
      expect(button).toBeDisabled()
      portal.release()

      await vi.waitFor(() => expect(redirect).toHaveBeenCalledWith(PORTAL_URL))
      expect(button).toBeDisabled()
    })

    it("reports the API's reason when the portal can't open", async () => {
      serveOrganization()
      server.use(
        http.post(apiUrl(PORTAL_PATH), () =>
          HttpResponse.json(
            { detail: 'Your organization has no billing account yet; subscribe first.' },
            { status: 400 },
          ),
        ),
      )
      const { user } = renderRoute('/billing', { signedInAs: admin })

      await user.click(await screen.findByRole('button', { name: 'Manage billing' }))

      expect(
        await screen.findByText('Your organization has no billing account yet; subscribe first.'),
      ).toBeInTheDocument()
      expect(redirect).not.toHaveBeenCalled()
    })
  })

  describe('the billing email', () => {
    it('saves a new address', async () => {
      serveOrganization()
      const update = spyResolver(() =>
        HttpResponse.json(buildOrganization({ billing_email: 'invoices@acme.test' })),
      )
      server.use(http.patch(apiUrl(PROFILE_PATH), update))
      const { user } = renderRoute('/billing', { signedInAs: admin })

      const field = await screen.findByLabelText('Billing email')
      await user.clear(field)
      await user.type(field, 'invoices@acme.test')
      await user.click(screen.getByRole('button', { name: 'Save billing email' }))

      expect(await screen.findByText('Billing email saved.')).toBeInTheDocument()
      expect(await update.mock.calls[0][0].request.json()).toEqual({
        billing_email: 'invoices@acme.test',
      })
    })

    it('sends an emptied address as none', async () => {
      serveOrganization()
      const update = spyResolver(() =>
        HttpResponse.json(buildOrganization({ billing_email: null })),
      )
      server.use(http.patch(apiUrl(PROFILE_PATH), update))
      const { user } = renderRoute('/billing', { signedInAs: admin })

      await user.clear(await screen.findByLabelText('Billing email'))
      await user.click(screen.getByRole('button', { name: 'Save billing email' }))

      expect(await screen.findByText('Billing email saved.')).toBeInTheDocument()
      expect(await update.mock.calls[0][0].request.json()).toEqual({ billing_email: null })
    })

    it("shows the server's error under the field", async () => {
      serveOrganization()
      server.use(
        http.patch(apiUrl(PROFILE_PATH), () =>
          HttpResponse.json(
            { billing_email: ['An organization with this billing email already exists.'] },
            { status: 400 },
          ),
        ),
      )
      const { user } = renderRoute('/billing', { signedInAs: admin })

      const field = await screen.findByLabelText('Billing email')
      await user.clear(field)
      await user.type(field, 'taken@example.com')
      await user.click(screen.getByRole('button', { name: 'Save billing email' }))

      expect(await screen.findByLabelText('Billing email')).toHaveAccessibleDescription(
        'An organization with this billing email already exists.',
      )
    })
  })

  it('offers the plans if the organization turns out to have no subscription', async () => {
    serveOrganization(buildOrganization({ active_subscription: null }))
    server.use(
      http.get(apiUrl('/subscriptions/prices/'), () =>
        HttpResponse.json({ count: 1, results: [buildPrice()] }),
      ),
    )
    renderRoute('/billing', { signedInAs: admin })

    expect(await screen.findByRole('list', { name: 'Plans' })).toBeInTheDocument()
  })

  it('offers a retry when loading fails', async () => {
    server.use(http.get(apiUrl(PROFILE_PATH), () => HttpResponse.json({}, { status: 500 })))
    const { user } = renderRoute('/billing', { signedInAs: admin })

    const retry = await screen.findByRole('button', { name: 'Try again' })
    serveOrganization()
    await user.click(retry)

    expect(await screen.findByText('Yearly plan')).toBeInTheDocument()
  })

  it('is for admins only', () => {
    renderRoute('/billing', { signedInAs: buildCurrentUser() })

    expect(screen.getByRole('heading', { name: "You don't have access" })).toBeInTheDocument()
  })
})
