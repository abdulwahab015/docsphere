import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { getAccessToken } from '@/api/access-token'
import { buildCurrentUser, buildOrganizationSummary } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const LOGOUT_PATH = '/users/auth/logout/'

// The lapsed-subscription screen is where the standalone button appears.
function renderLapsedOrganization() {
  return renderRoute('/', {
    signedInAs: buildCurrentUser({
      organization: buildOrganizationSummary({ has_active_subscription: false }),
    }),
  })
}

describe('LogoutButton', () => {
  it('ends the session and returns to the login page', async () => {
    const logout = spyResolver(() => new HttpResponse(null, { status: 205 }))
    server.use(http.post(apiUrl(LOGOUT_PATH), logout))
    const { user } = renderLapsedOrganization()

    await user.click(screen.getByRole('button', { name: 'Log out' }))

    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(logout).toHaveBeenCalledTimes(1)
    expect(getAccessToken()).toBeNull()
  })

  it('still signs out locally when the server call fails', async () => {
    server.use(
      http.post(apiUrl(LOGOUT_PATH), () =>
        HttpResponse.json({ detail: 'refresh token is required.' }, { status: 400 }),
      ),
    )
    const { user } = renderLapsedOrganization()

    await user.click(screen.getByRole('button', { name: 'Log out' }))

    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
  })
})
