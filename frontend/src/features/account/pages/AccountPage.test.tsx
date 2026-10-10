import { screen, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'

import { getAccessToken } from '@/api/access-token'
import { authKeys } from '@/features/auth/query-keys'
import { MAX_NAME_LENGTH } from '@/lib/schemas'
import { findAccountMenu } from '@/test/actions'
import { buildCurrentUser, buildTokenPair } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const PASSWORD_PATH = '/users/me/password/'
const ME_PATH = '/users/me/'
const EMAIL_PATH = '/users/me/email/'
const CURRENT_PASSWORD = 'Old-Pass-123!'
const NEW_PASSWORD = 'New-Pass-456!'

// Both forms ask for the current password.
function passwordForm() {
  return within(screen.getByRole('form', { name: 'Password' }))
}

async function fillPasswordForm(
  user: UserEvent,
  {
    current = CURRENT_PASSWORD,
    next = NEW_PASSWORD,
    confirm = next,
  }: { current?: string; next?: string; confirm?: string } = {},
) {
  const fields: [string, string][] = [
    ['Current password', current],
    ['New password', next],
    ['Confirm new password', confirm],
  ]
  for (const [label, value] of fields) {
    // Left blank when there's nothing to type.
    if (value) {
      await user.type(passwordForm().getByLabelText(label), value)
    }
  }
  await user.click(passwordForm().getByRole('button', { name: 'Change password' }))
}

function rejectPasswordChange(errors: Record<string, string[]>) {
  server.use(http.post(apiUrl(PASSWORD_PATH), () => HttpResponse.json(errors, { status: 400 })))
}

describe('AccountPage', () => {
  it('shows who is signed in, their role and their organization', () => {
    renderRoute('/settings/account', { signedInAs: buildCurrentUser() })

    expect(screen.getByRole('heading', { level: 1, name: 'Account' })).toBeInTheDocument()
    const labels = screen.getAllByRole('term').map((term) => term.textContent)
    const values = screen.getAllByRole('definition').map((definition) => definition.textContent)
    expect(labels).toEqual(['Email', 'Role', 'Organization'])
    expect(values).toEqual(['ada@example.com', 'Member', 'Acme'])
  })

  describe('naming yourself', () => {
    const ada = buildCurrentUser({ name: 'Ada' })

    function serveNameChange(response: () => Response) {
      const change = spyResolver(response)
      server.use(http.patch(apiUrl(ME_PATH), change))
      return change
    }

    it('saves a new name, which every screen shows at once', async () => {
      const change = serveNameChange(() =>
        HttpResponse.json(buildCurrentUser({ name: 'Ada Lovelace' })),
      )
      const { user } = renderRoute('/settings/account', { signedInAs: ada })
      const field = screen.getByLabelText('Your name')
      const save = screen.getByRole('button', { name: 'Save name' })
      expect(field).toHaveValue('Ada')
      expect(save).toBeDisabled()

      await user.clear(field)
      await user.type(field, '  Ada Lovelace ')
      await user.click(save)

      expect(await screen.findByText('Name saved.')).toBeInTheDocument()
      expect(await change.mock.calls[0][0].request.json()).toEqual({ name: 'Ada Lovelace' })
      expect(await findAccountMenu()).toHaveTextContent('Ada Lovelace')
      expect(field).toHaveValue('Ada Lovelace')
      expect(save).toBeDisabled()
    })

    it('removes the name, after which the email address stands in for it', async () => {
      serveNameChange(() => HttpResponse.json(buildCurrentUser({ name: '' })))
      const { user } = renderRoute('/settings/account', { signedInAs: ada })

      await user.clear(screen.getByLabelText('Your name'))
      await user.click(screen.getByRole('button', { name: 'Save name' }))

      expect(await screen.findByText('Name removed.')).toBeInTheDocument()
      expect(await findAccountMenu()).toHaveTextContent('ada@example.com')
    })

    it("shows the server's reason under the field", async () => {
      serveNameChange(() =>
        HttpResponse.json({ name: ['This name is not allowed.'] }, { status: 400 }),
      )
      const { user } = renderRoute('/settings/account', { signedInAs: ada })

      await user.type(screen.getByLabelText('Your name'), ' Lovelace')
      await user.click(screen.getByRole('button', { name: 'Save name' }))

      expect(await screen.findByText('This name is not allowed.')).toBeInTheDocument()
    })

    it('refuses a name over the length limit without sending it', async () => {
      const change = serveNameChange(() => HttpResponse.json(ada))
      const { user } = renderRoute('/settings/account', { signedInAs: ada })

      await user.click(screen.getByLabelText('Your name'))
      await user.paste('x'.repeat(MAX_NAME_LENGTH))
      await user.click(screen.getByRole('button', { name: 'Save name' }))

      expect(
        await screen.findByText(`Use at most ${MAX_NAME_LENGTH} characters.`),
      ).toBeInTheDocument()
      expect(change).not.toHaveBeenCalled()
    })
  })

  describe('changing the email', () => {
    function emailForm() {
      return within(screen.getByRole('form', { name: 'Change email' }))
    }

    async function requestEmailChange(user: UserEvent, newEmail = 'grace@example.com') {
      await user.type(emailForm().getByLabelText('New email'), newEmail)
      await user.type(emailForm().getByLabelText('Current password'), CURRENT_PASSWORD)
      await user.click(emailForm().getByRole('button', { name: 'Send confirmation link' }))
    }

    it('sends a link to the new address and changes nothing yet', async () => {
      const request = spyResolver(() => new HttpResponse(null, { status: 204 }))
      server.use(http.post(apiUrl(EMAIL_PATH), request))
      const { user, queryClient } = renderRoute('/settings/account', {
        signedInAs: buildCurrentUser(),
      })

      await requestEmailChange(user)

      expect(
        await screen.findByText('Check grace@example.com for a link to confirm the change.'),
      ).toBeInTheDocument()
      expect(await request.mock.calls[0][0].request.json()).toEqual({
        new_email: 'grace@example.com',
        current_password: CURRENT_PASSWORD,
      })
      expect(emailForm().getByLabelText('New email')).toHaveValue('')
      expect(emailForm().getByLabelText('Current password')).toHaveValue('')
      expect(queryClient.getQueryData(authKeys.currentUser)).toEqual(buildCurrentUser())
    })

    it("shows the server's reasons under the fields", async () => {
      server.use(
        http.post(apiUrl(EMAIL_PATH), () =>
          HttpResponse.json(
            {
              new_email: ['This email address is already in use.'],
              current_password: ['Current password is incorrect.'],
            },
            { status: 400 },
          ),
        ),
      )
      const { user } = renderRoute('/settings/account', { signedInAs: buildCurrentUser() })

      await requestEmailChange(user)

      expect(await emailForm().findByLabelText('New email')).toHaveAccessibleDescription(
        'This email address is already in use.',
      )
      expect(emailForm().getByLabelText('Current password')).toHaveAccessibleDescription(
        'Current password is incorrect.',
      )
    })

    it('checks the address before sending it', async () => {
      const request = spyResolver(() => new HttpResponse(null, { status: 204 }))
      server.use(http.post(apiUrl(EMAIL_PATH), request))
      const { user } = renderRoute('/settings/account', { signedInAs: buildCurrentUser() })

      await requestEmailChange(user, 'not-an-email')

      expect(await emailForm().findByLabelText('New email')).toBeInvalid()
      expect(request).not.toHaveBeenCalled()
    })
  })

  describe('changing the password', () => {
    it('sends the current and new password, and keeps this session going', async () => {
      const change = spyResolver(() =>
        HttpResponse.json(buildTokenPair({ access: 'renewed-access-token' })),
      )
      server.use(http.post(apiUrl(PASSWORD_PATH), change))
      const { user } = renderRoute('/settings/account', { signedInAs: buildCurrentUser() })

      await fillPasswordForm(user)

      expect(
        await screen.findByText('Password changed. Your other devices have been signed out.'),
      ).toBeInTheDocument()
      expect(await change.mock.calls[0][0].request.json()).toEqual({
        current_password: CURRENT_PASSWORD,
        new_password: NEW_PASSWORD,
      })
      expect(getAccessToken()).toBe('renewed-access-token')
      expect(passwordForm().getByLabelText('Current password')).toHaveValue('')
      expect(screen.getByLabelText('New password')).toHaveValue('')
      expect(screen.getByLabelText('Confirm new password')).toHaveValue('')
      expect(screen.getByRole('heading', { level: 1, name: 'Account' })).toBeInTheDocument()
    })

    it('reports a wrong current password under that field', async () => {
      rejectPasswordChange({ current_password: ['Current password is incorrect.'] })
      const { user } = renderRoute('/settings/account', { signedInAs: buildCurrentUser() })

      await fillPasswordForm(user)

      expect(await passwordForm().findByLabelText('Current password')).toHaveAccessibleDescription(
        'Current password is incorrect.',
      )
    })

    it("shows the server's reason for refusing the new password under it", async () => {
      rejectPasswordChange({ new_password: ['The password is too similar to the email address.'] })
      const { user } = renderRoute('/settings/account', { signedInAs: buildCurrentUser() })

      await fillPasswordForm(user)

      expect(
        await screen.findByText('The password is too similar to the email address.'),
      ).toBeVisible()
      expect(screen.getByLabelText('New password')).toBeInvalid()
    })

    it('reports a refusal that belongs to no field above the form', async () => {
      server.use(
        http.post(apiUrl(PASSWORD_PATH), () =>
          HttpResponse.json(
            { detail: 'Request was throttled. Expected available in 3600 seconds.' },
            { status: 429 },
          ),
        ),
      )
      const { user } = renderRoute('/settings/account', { signedInAs: buildCurrentUser() })

      await fillPasswordForm(user)

      expect(await screen.findByRole('alert')).toHaveTextContent(/throttled/)
    })

    it('checks the new password before sending it', async () => {
      const change = spyResolver(() => HttpResponse.json(buildTokenPair()))
      server.use(http.post(apiUrl(PASSWORD_PATH), change))
      const { user } = renderRoute('/settings/account', { signedInAs: buildCurrentUser() })

      await fillPasswordForm(user, { current: '', next: 'weak', confirm: 'different' })

      expect(await screen.findByText('Enter your current password.')).toBeVisible()
      expect(screen.getByText('Use at least 8 characters.')).toBeVisible()
      expect(screen.getByText('Passwords do not match.')).toBeVisible()
      expect(change).not.toHaveBeenCalled()
    })
  })
})
