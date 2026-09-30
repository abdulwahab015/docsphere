import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { buildCurrentUser, buildTokenPair } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const ACCEPT_PATH = '/users/invitations/accept/'
const INVITE_LINK = '/accept-invite?token=invite-token'
const PASSWORD = 'Sup3r-secret!'

async function choosePassword(user: ReturnType<typeof renderRoute>['user']) {
  await user.type(await screen.findByLabelText('Password'), PASSWORD)
  await user.type(screen.getByLabelText('Confirm password'), PASSWORD)
  await user.click(screen.getByRole('button', { name: 'Create account' }))
}

describe('AcceptInvitePage', () => {
  it('creates the account, signs in, and opens the app', async () => {
    const accept = spyResolver(() => HttpResponse.json(buildTokenPair(), { status: 201 }))
    server.use(
      http.post(apiUrl(ACCEPT_PATH), accept),
      http.get(apiUrl('/users/me/'), () => HttpResponse.json(buildCurrentUser())),
    )
    const { router, user } = renderRoute(INVITE_LINK)

    await choosePassword(user)

    expect(await screen.findByText(/Signed in as ada@example.com/)).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
    expect(await accept.mock.calls[0][0].request.json()).toEqual({
      token: 'invite-token',
      password: PASSWORD,
    })
  })

  it('shows why an unusable invitation was rejected', async () => {
    server.use(
      http.post(apiUrl(ACCEPT_PATH), () =>
        HttpResponse.json(
          { token: ['This invitation link is invalid or has expired.'] },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderRoute(INVITE_LINK)

    await choosePassword(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This invitation link is invalid or has expired.',
    )
  })

  it('rejects a link without a token', () => {
    renderRoute('/accept-invite')

    expect(screen.getByRole('heading', { name: 'Invalid invitation link' })).toBeInTheDocument()
  })
})
