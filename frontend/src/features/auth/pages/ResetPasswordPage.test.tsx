import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const RESET_CONFIRM_PATH = '/users/auth/password-reset/confirm/'
const RESET_LINK = '/reset-password?uid=MQ&token=abc-123'
const NEW_PASSWORD = 'N3w-secret!'

async function submitNewPassword(user: ReturnType<typeof renderRoute>['user']) {
  await user.type(await screen.findByLabelText('New password'), NEW_PASSWORD)
  await user.type(screen.getByLabelText('Confirm new password'), NEW_PASSWORD)
  await user.click(screen.getByRole('button', { name: 'Update password' }))
}

describe('ResetPasswordPage', () => {
  it('sets the new password using the uid and token from the link', async () => {
    const confirmReset = spyResolver(() => new HttpResponse(null, { status: 200 }))
    server.use(http.post(apiUrl(RESET_CONFIRM_PATH), confirmReset))
    const { user } = renderRoute(RESET_LINK)

    await submitNewPassword(user)

    expect(await screen.findByRole('heading', { name: 'Password updated' })).toBeInTheDocument()
    expect(await confirmReset.mock.calls[0][0].request.json()).toEqual({
      uid: 'MQ',
      token: 'abc-123',
      new_password: NEW_PASSWORD,
    })
  })

  it('explains when the server rejects the link', async () => {
    server.use(
      http.post(apiUrl(RESET_CONFIRM_PATH), () =>
        HttpResponse.json(
          { non_field_errors: ['Invalid or expired reset link.'] },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderRoute(RESET_LINK)

    await submitNewPassword(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid or expired reset link.')
    expect(screen.getByRole('link', { name: 'Request a new link' })).toBeInTheDocument()
  })

  it('rejects a link missing its uid or token', () => {
    renderRoute('/reset-password?uid=MQ')

    expect(screen.getByRole('heading', { name: 'Invalid reset link' })).toBeInTheDocument()
    expect(screen.queryByLabelText('New password')).not.toBeInTheDocument()
  })
})
