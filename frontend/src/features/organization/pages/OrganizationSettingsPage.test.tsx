import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { Organization } from '@/api/types'
import { buildCurrentUser } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const PROFILE_PATH = '/organizations/profile/'
const SETTINGS_URL = '/settings/organization'

const admin = buildCurrentUser({ org_role: 'ADMIN' })

function buildOrganization(overrides: Partial<Organization> = {}): Organization {
  return {
    id: 1,
    name: 'Acme',
    billing_email: 'billing@acme.test',
    active_subscription: {
      id: 'sub_1',
      status: 'active',
      interval: 'year',
      current_period_end: '2027-03-01T12:00:00Z',
      cancel_at_period_end: false,
    },
    created: '2026-01-01T00:00:00Z',
    modified: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function serveOrganization(organization = buildOrganization()) {
  server.use(http.get(apiUrl(PROFILE_PATH), () => HttpResponse.json(organization)))
}

describe('OrganizationSettingsPage', () => {
  it("shows the organization's details and subscription", async () => {
    serveOrganization()
    renderRoute(SETTINGS_URL, { signedInAs: admin })

    expect(await screen.findByLabelText('Organization name')).toHaveValue('Acme')
    expect(screen.getByLabelText('Billing email')).toHaveValue('billing@acme.test')
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Yearly plan')).toBeInTheDocument()
    expect(screen.getByText(/^Renews on /)).toBeInTheDocument()
  })

  it("says when the subscription won't renew", async () => {
    const organization = buildOrganization()
    serveOrganization({
      ...organization,
      active_subscription: { ...organization.active_subscription!, cancel_at_period_end: true },
    })
    renderRoute(SETTINGS_URL, { signedInAs: admin })

    expect(await screen.findByText(/^Ends on /)).toBeInTheDocument()
  })

  it('leaves out the renewal date when Stripe has not reported one', async () => {
    const organization = buildOrganization()
    serveOrganization({
      ...organization,
      active_subscription: { ...organization.active_subscription!, current_period_end: null },
    })
    renderRoute(SETTINGS_URL, { signedInAs: admin })

    expect(await screen.findByText('Yearly plan')).toBeInTheDocument()
    expect(screen.queryByText(/^(Renews|Ends) on /)).not.toBeInTheDocument()
  })

  it('shows when there is no active subscription', async () => {
    serveOrganization(buildOrganization({ active_subscription: null, billing_email: null }))
    renderRoute(SETTINGS_URL, { signedInAs: admin })

    expect(await screen.findByText('No active subscription')).toBeInTheDocument()
    expect(screen.getByLabelText('Billing email')).toHaveValue('')
  })

  it('saves changes, confirms, and updates the name shown in the app', async () => {
    serveOrganization()
    const update = spyResolver(() =>
      HttpResponse.json(buildOrganization({ name: 'Acme Corp', billing_email: null })),
    )
    server.use(
      http.patch(apiUrl(PROFILE_PATH), update),
      http.get(apiUrl('/users/me/'), () =>
        HttpResponse.json({
          ...admin,
          organization: { ...admin.organization, name: 'Acme Corp' },
        }),
      ),
    )
    const { user } = renderRoute(SETTINGS_URL, { signedInAs: admin })
    const nameInput = await screen.findByLabelText('Organization name')

    await user.clear(nameInput)
    await user.type(nameInput, 'Acme Corp')
    await user.clear(screen.getByLabelText('Billing email'))
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByText('Organization details saved.')).toBeInTheDocument()
    expect(await update.mock.calls[0][0].request.json()).toEqual({
      name: 'Acme Corp',
      billing_email: null,
    })
    expect(await screen.findByRole('button', { name: 'Account menu' })).toHaveTextContent(
      'Admin · Acme Corp',
    )
  })

  it("shows the server's errors under the matching field", async () => {
    serveOrganization()
    server.use(
      http.patch(apiUrl(PROFILE_PATH), () =>
        HttpResponse.json(
          { billing_email: ['An organization with this billing email already exists.'] },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderRoute(SETTINGS_URL, { signedInAs: admin })
    const billingEmail = await screen.findByLabelText('Billing email')

    await user.clear(billingEmail)
    await user.type(billingEmail, 'taken@example.com')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByLabelText('Billing email')).toHaveAccessibleDescription(
      expect.stringContaining('An organization with this billing email already exists.'),
    )
  })

  it('offers a retry when loading fails', async () => {
    server.use(http.get(apiUrl(PROFILE_PATH), () => HttpResponse.json({}, { status: 500 })))
    const { user } = renderRoute(SETTINGS_URL, { signedInAs: admin })

    expect(await screen.findByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument()

    serveOrganization()
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByLabelText('Organization name')).toHaveValue('Acme')
  })

  it("tells members they don't have access, without calling the API", () => {
    renderRoute(SETTINGS_URL, { signedInAs: buildCurrentUser({ org_role: 'MEMBER' }) })

    expect(screen.getByRole('heading', { name: "You don't have access" })).toBeInTheDocument()
  })

  it('shows "no access" if the API refuses', async () => {
    server.use(
      http.get(apiUrl(PROFILE_PATH), () =>
        HttpResponse.json({ detail: 'Not allowed.' }, { status: 403 }),
      ),
    )
    renderRoute(SETTINGS_URL, { signedInAs: admin })

    expect(
      await screen.findByRole('heading', { name: "You don't have access" }),
    ).toBeInTheDocument()
  })
})
