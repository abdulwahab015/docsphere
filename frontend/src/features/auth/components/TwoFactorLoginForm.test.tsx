import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { findAccountMenu } from '@/test/actions'
import { buildCurrentUser, buildTokenPair } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const LOGIN_PATH = '/users/auth/login/'
const TWO_FACTOR_LOGIN_PATH = '/users/auth/login/two-factor/'
const CHALLENGE = { two_factor_token: 'signed-challenge' }

/** The password is right, and the account has two-factor sign-in on. */
function servePasswordStep() {
  const login = spyResolver(() => HttpResponse.json(CHALLENGE))
  server.use(
    http.post(apiUrl(LOGIN_PATH), login),
    http.get(apiUrl('/users/me/'), ({ request }) =>
      request.headers.get('Authorization') === 'Bearer new-access-token'
        ? HttpResponse.json(buildCurrentUser({ two_factor_enabled: true }))
        : HttpResponse.json({}, { status: 401 }),
    ),
  )
  return login
}

function serveCodeStep(response: () => Response = () => HttpResponse.json(buildTokenPair())) {
  const codeStep = spyResolver(response)
  server.use(http.post(apiUrl(TWO_FACTOR_LOGIN_PATH), codeStep))
  return codeStep
}

async function logInWithPassword(user: ReturnType<typeof renderRoute>['user']) {
  await user.type(await screen.findByLabelText('Email'), 'ada@example.com')
  await user.type(screen.getByLabelText('Password'), 'Sup3r-secret!')
  await user.click(screen.getByRole('button', { name: 'Log in' }))
  await screen.findByRole('heading', { name: 'Two-factor sign-in' })
}

describe('TwoFactorLoginForm', () => {
  it('asks for a code after the password, and logs in with it', async () => {
    servePasswordStep()
    const codeStep = serveCodeStep()
    const { user } = renderRoute('/login')

    await logInWithPassword(user)
    // Nobody is signed in yet.
    expect(screen.queryByRole('button', { name: 'Account menu' })).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Code from your app'), '123456')
    await user.click(screen.getByRole('button', { name: 'Verify' }))

    expect(await findAccountMenu()).toHaveTextContent('ada@example.com')
    expect(await codeStep.mock.calls[0][0].request.json()).toEqual({
      two_factor_token: 'signed-challenge',
      otp: '123456',
    })
  })

  it('takes a recovery code instead', async () => {
    servePasswordStep()
    const codeStep = serveCodeStep()
    const { user } = renderRoute('/login')

    await logInWithPassword(user)
    await user.type(screen.getByLabelText('Code from your app'), '12')
    await user.click(screen.getByRole('button', { name: 'Use a recovery code' }))
    // The half-typed app code is gone.
    expect(screen.getByLabelText('Recovery code')).toHaveValue('')
    await user.type(screen.getByLabelText('Recovery code'), 'abcde-fghjk')
    await user.click(screen.getByRole('button', { name: 'Verify' }))

    await findAccountMenu()
    expect(await codeStep.mock.calls[0][0].request.json()).toMatchObject({ otp: 'abcde-fghjk' })
  })

  it('can switch back to a code from the app', async () => {
    servePasswordStep()
    const { user } = renderRoute('/login')

    await logInWithPassword(user)
    await user.click(screen.getByRole('button', { name: 'Use a recovery code' }))
    await user.click(screen.getByRole('button', { name: 'Use a code from your app' }))

    expect(screen.getByLabelText('Code from your app')).toHaveAttribute('inputmode', 'numeric')
  })

  it("puts the API's reason under the code when it's wrong", async () => {
    servePasswordStep()
    serveCodeStep(() => HttpResponse.json({ otp: ["That code didn't work."] }, { status: 400 }))
    const { user } = renderRoute('/login')

    await logInWithPassword(user)
    await user.type(screen.getByLabelText('Code from your app'), '000000')
    await user.click(screen.getByRole('button', { name: 'Verify' }))

    expect(await screen.findByText("That code didn't work.")).toBeInTheDocument()
    expect(screen.getByLabelText('Code from your app')).toHaveAttribute('aria-invalid', 'true')
  })

  it('asks for a code before sending anything', async () => {
    servePasswordStep()
    const codeStep = serveCodeStep()
    const { user } = renderRoute('/login')

    await logInWithPassword(user)
    await user.click(screen.getByRole('button', { name: 'Verify' }))

    expect(await screen.findByText('Enter the code.')).toBeInTheDocument()
    expect(codeStep).not.toHaveBeenCalled()
  })

  it('goes back to the password, saying why, once the sign-in has expired', async () => {
    servePasswordStep()
    serveCodeStep(() =>
      HttpResponse.json(
        { two_factor_token: ['Your sign-in has expired. Log in again.'] },
        { status: 400 },
      ),
    )
    const { user } = renderRoute('/login')

    await logInWithPassword(user)
    await user.type(screen.getByLabelText('Code from your app'), '123456')
    await user.click(screen.getByRole('button', { name: 'Verify' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Your sign-in has expired. Log in again.',
    )
    expect(screen.getByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveValue('ada@example.com')
    expect(screen.getByLabelText('Password')).toHaveValue('')
  })

  it('lets someone else log in instead', async () => {
    servePasswordStep()
    const { user } = renderRoute('/login')

    await logInWithPassword(user)
    await user.click(screen.getByRole('button', { name: 'Log in as someone else' }))

    expect(screen.getByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
