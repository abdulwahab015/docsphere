import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { findAccountMenu } from '@/test/actions'
import { buildCurrentUser } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const RESEND_PATH = '/users/me/verification-email/'
const unverifiedAdmin = buildCurrentUser({
  email: 'new-admin@example.com',
  email_verified: false,
  org_role: 'ADMIN',
})

describe('RequireVerifiedEmail', () => {
  it('lets a verified user into the app', async () => {
    renderRoute('/', { signedInAs: buildCurrentUser() })

    expect(await findAccountMenu()).toBeInTheDocument()
  })

  it('asks a new signup to verify their address before anything else', () => {
    renderRoute('/projects', { signedInAs: unverifiedAdmin })

    expect(screen.getByRole('heading', { name: 'Check your email' })).toBeInTheDocument()
    expect(screen.getByText('new-admin@example.com')).toBeInTheDocument()
    expect(screen.getByText('Wrong address? Log out and sign up again.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Account menu' })).not.toBeInTheDocument()
  })

  it('comes before the subscription: a new organization verifies, then subscribes', () => {
    renderRoute('/', {
      signedInAs: {
        ...unverifiedAdmin,
        organization: { ...unverifiedAdmin.organization!, has_active_subscription: false },
      },
    })

    expect(screen.getByRole('heading', { name: 'Check your email' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Subscribe to continue' })).not.toBeInTheDocument()
  })

  it('sends a new link on request', async () => {
    const resend = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(http.post(apiUrl(RESEND_PATH), resend))
    const { user } = renderRoute('/', { signedInAs: unverifiedAdmin })

    await user.click(screen.getByRole('button', { name: 'Send a new link' }))

    expect(
      await screen.findByText('A new link is on its way to new-admin@example.com.'),
    ).toBeInTheDocument()
    expect(resend).toHaveBeenCalledOnce()
  })

  it('says so when a new link could not be sent', async () => {
    server.use(
      http.post(apiUrl(RESEND_PATH), () =>
        HttpResponse.json({ detail: 'Request was throttled.' }, { status: 429 }),
      ),
    )
    const { user } = renderRoute('/', { signedInAs: unverifiedAdmin })

    await user.click(screen.getByRole('button', { name: 'Send a new link' }))

    expect(
      await screen.findByText("Couldn't send a new link. Try again later."),
    ).toBeInTheDocument()
  })
})
