import { screen } from '@testing-library/react'

import { findAccountMenu } from '@/test/actions'
import { buildCurrentUser } from '@/test/factories'
import { renderRoute } from '@/test/render'

const lapsedOrganization = { id: 1, name: 'Acme', has_active_subscription: false }

describe('RequireActiveSubscription', () => {
  it('lets members of a subscribed organization through', async () => {
    renderRoute('/', { signedInAs: buildCurrentUser() })

    expect(await findAccountMenu()).toBeInTheDocument()
  })

  it('asks an admin to subscribe', () => {
    renderRoute('/', {
      signedInAs: buildCurrentUser({ org_role: 'ADMIN', organization: lapsedOrganization }),
    })

    expect(screen.getByRole('heading', { name: 'Subscription inactive' })).toBeInTheDocument()
    expect(screen.getByText(/Subscribe to a plan/)).toBeInTheDocument()
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
