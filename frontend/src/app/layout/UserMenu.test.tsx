import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { getAccessToken } from '@/api/access-token'
import { logOutViaAccountMenu } from '@/test/actions'
import { buildCurrentUser } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

describe('UserMenu', () => {
  it('shows who is signed in, their role, and their organization', () => {
    renderRoute('/', { signedInAs: buildCurrentUser({ org_role: 'ADMIN' }) })

    const menuButton = screen.getByRole('button', { name: 'Account menu' })
    expect(menuButton).toHaveTextContent('ada@example.com')
    expect(menuButton).toHaveTextContent('Admin · Acme')
  })

  it('opens account settings', async () => {
    server.use(http.get(apiUrl('/users/'), () => HttpResponse.json({ count: 0, results: [] })))
    const { user } = renderRoute('/people', { signedInAs: buildCurrentUser() })

    await user.click(screen.getByRole('button', { name: 'Account menu' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Account settings' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Account' })).toBeInTheDocument()
  })

  it("doesn't send the next person to sign in back to the previous user's page", async () => {
    server.use(
      http.post(apiUrl('/users/auth/logout/'), () => new HttpResponse(null, { status: 205 })),
      http.get(apiUrl('/users/'), () => HttpResponse.json({ count: 0, results: [] })),
    )
    const { router, user } = renderRoute('/people', { signedInAs: buildCurrentUser() })

    await logOutViaAccountMenu(user)

    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(router.state.location.state).toBeNull()
  })

  it('logs out and returns to the login page', async () => {
    const logout = spyResolver(() => new HttpResponse(null, { status: 205 }))
    server.use(http.post(apiUrl('/users/auth/logout/'), logout))
    const { user } = renderRoute('/', { signedInAs: buildCurrentUser() })

    await logOutViaAccountMenu(user)

    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(logout).toHaveBeenCalledTimes(1)
    expect(getAccessToken()).toBeNull()
  })
})
