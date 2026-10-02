import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { findAccountMenu } from '@/test/actions'
import { buildCurrentUser, buildOrganization, buildPrice } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server } from '@/test/server'

const lapsedOrganization = { id: 1, name: 'Acme', has_active_subscription: false }

function serveLapsedBilling() {
  server.use(
    http.get(apiUrl('/organizations/profile/'), () =>
      HttpResponse.json(buildOrganization({ active_subscription: null })),
    ),
    http.get(apiUrl('/subscriptions/prices/'), () =>
      HttpResponse.json({ count: 1, results: [buildPrice()] }),
    ),
  )
}

describe('RequireActiveSubscription', () => {
  it('lets members of a subscribed organization through', async () => {
    renderRoute('/', { signedInAs: buildCurrentUser() })

    expect(await findAccountMenu()).toBeInTheDocument()
  })

  it('offers an admin the plans to subscribe to', async () => {
    serveLapsedBilling()
    renderRoute('/', {
      signedInAs: buildCurrentUser({ org_role: 'ADMIN', organization: lapsedOrganization }),
    })

    expect(screen.getByRole('heading', { name: 'Subscribe to continue' })).toBeInTheDocument()
    expect(screen.getByText(/Acme doesn't have an active subscription/)).toBeInTheDocument()
    expect(await screen.findByRole('list', { name: 'Plans' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Account menu' })).not.toBeInTheDocument()
  })

  it('turns away an account that belongs to no organization', () => {
    renderRoute('/', { signedInAs: buildCurrentUser({ organization: null }) })

    expect(screen.getByRole('heading', { name: 'No organization' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument()
  })

  it('tells a member to ask their admin', () => {
    renderRoute('/', {
      signedInAs: buildCurrentUser({ org_role: 'MEMBER', organization: lapsedOrganization }),
    })

    expect(screen.getByText(/Ask your organization admin to renew it/)).toBeInTheDocument()
  })
})
