import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { REFRESH_PATH } from '@/api/constants'
import { findAccountMenu } from '@/test/actions'
import { buildCurrentUser, buildTokenPair } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const LOGIN_PATH = '/users/auth/login/'

function serveLogin() {
  const login = spyResolver(() => HttpResponse.json(buildTokenPair()))
  const me = spyResolver(({ request }) =>
    request.headers.get('Authorization') === 'Bearer new-access-token'
      ? HttpResponse.json(buildCurrentUser())
      : HttpResponse.json({}, { status: 401 }),
  )
  server.use(http.post(apiUrl(LOGIN_PATH), login), http.get(apiUrl('/users/me/'), me))
  return login
}

async function fillAndSubmit(user: ReturnType<typeof renderRoute>['user']) {
  await user.type(await screen.findByLabelText('Email'), 'ada@example.com')
  await user.type(screen.getByLabelText('Password'), 'Sup3r-secret!')
  await user.click(screen.getByRole('button', { name: 'Log in' }))
}

describe('LoginPage', () => {
  it('logs in and lands on the home page', async () => {
    const login = serveLogin()
    const { user } = renderRoute('/login')

    await fillAndSubmit(user)

    expect(await findAccountMenu()).toHaveTextContent('ada@example.com')
    expect(await login.mock.calls[0][0].request.json()).toEqual({
      email: 'ada@example.com',
      password: 'Sup3r-secret!',
    })
  })

  it('returns to the page the user was headed to', async () => {
    serveLogin()
    server.use(http.get(apiUrl('/users/'), () => HttpResponse.json({ count: 0, results: [] })))
    const { router, user } = renderRoute('/people?search=ada')

    await fillAndSubmit(user)

    await findAccountMenu()
    expect(router.state.location).toMatchObject({ pathname: '/people', search: '?search=ada' })
  })

  it("shows the server's message for wrong credentials without refreshing", async () => {
    const refresh = spyResolver(() => HttpResponse.json({}, { status: 400 }))
    server.use(
      http.post(apiUrl(REFRESH_PATH), refresh),
      http.post(apiUrl(LOGIN_PATH), () =>
        HttpResponse.json(
          {
            detail: 'No active account found with the given credentials',
            code: 'no_active_account',
          },
          { status: 401 },
        ),
      ),
    )
    const { user } = renderRoute('/login')

    await fillAndSubmit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No active account found with the given credentials',
    )
    // Only the initial session check on page load; the 401 didn't trigger another.
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('validates the form before sending anything', async () => {
    const login = serveLogin()
    const { user } = renderRoute('/login')

    await user.type(await screen.findByLabelText('Email'), 'not-an-email')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
    expect(login).not.toHaveBeenCalled()
  })
})
