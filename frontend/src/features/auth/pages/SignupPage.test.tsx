import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { buildCurrentUser, buildOrganization, buildTokenPair } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const SIGNUP_PATH = '/organizations/signup/'
const VALID_PASSWORD = 'Sup3r-secret!'

type TestUser = ReturnType<typeof renderRoute>['user']

interface PasswordInput {
  password?: string
  confirmation?: string
}

async function fillForm(
  user: TestUser,
  { password = VALID_PASSWORD, confirmation = password }: PasswordInput = {},
) {
  await user.type(await screen.findByLabelText('Organization name'), 'Acme')
  await user.type(screen.getByLabelText('Your email'), 'ada@example.com')
  await user.type(screen.getByLabelText('Password'), password)
  await user.type(screen.getByLabelText('Confirm password'), confirmation)
  await user.click(screen.getByRole('button', { name: 'Create organization' }))
}

describe('SignupPage', () => {
  it('creates the organization and signs the new admin in', async () => {
    const signup = spyResolver(() => HttpResponse.json(buildTokenPair(), { status: 201 }))
    const newAdmin = buildCurrentUser({
      org_role: 'ADMIN',
      organization: { id: 2, name: 'Acme', has_active_subscription: false },
    })
    server.use(
      http.post(apiUrl(SIGNUP_PATH), signup),
      http.get(apiUrl('/users/me/'), () => HttpResponse.json(newAdmin)),
      http.get(apiUrl('/organizations/profile/'), () =>
        HttpResponse.json(buildOrganization({ active_subscription: null, billing_email: null })),
      ),
      http.get(apiUrl('/subscriptions/prices/'), () =>
        HttpResponse.json({ count: 0, results: [] }),
      ),
    )
    const { user } = renderRoute('/signup')

    await fillForm(user)

    // A brand-new organization has no subscription yet: its admin picks a plan.
    expect(
      await screen.findByRole('heading', { name: 'Subscribe to continue' }),
    ).toBeInTheDocument()
    expect(await signup.mock.calls[0][0].request.json()).toEqual({
      name: 'Acme',
      billing_email: null,
      admin_email: 'ada@example.com',
      admin_password: VALID_PASSWORD,
    })
  })

  it("shows the server's field errors under the matching fields", async () => {
    server.use(
      http.post(apiUrl(SIGNUP_PATH), () =>
        HttpResponse.json(
          { admin_email: ['A user with this email already exists.'] },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderRoute('/signup')

    await fillForm(user)

    expect(await screen.findByLabelText('Your email')).toHaveAccessibleDescription(
      'A user with this email already exists.',
    )
  })

  it("shows the server's password-policy errors under the password field", async () => {
    server.use(
      http.post(apiUrl(SIGNUP_PATH), () =>
        HttpResponse.json({ admin_password: ['This password is too common.'] }, { status: 400 }),
      ),
    )
    const { user } = renderRoute('/signup')

    await fillForm(user)

    expect(await screen.findByLabelText('Password')).toHaveAccessibleDescription(
      expect.stringContaining('This password is too common.'),
    )
  })

  it('checks the password policy and confirmation before sending anything', async () => {
    const signup = spyResolver(() => HttpResponse.json(buildTokenPair(), { status: 201 }))
    server.use(http.post(apiUrl(SIGNUP_PATH), signup))
    const { user } = renderRoute('/signup')

    await fillForm(user, { password: 'weakpass', confirmation: 'different' })

    expect(await screen.findByText('Include an uppercase letter.')).toBeInTheDocument()
    expect(screen.getByText('Passwords do not match.')).toBeInTheDocument()
    expect(signup).not.toHaveBeenCalled()
  })
})
