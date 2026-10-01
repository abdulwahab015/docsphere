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
