import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { authKeys } from '@/features/auth/query-keys'
import { buildCurrentUser } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const CONFIRM_PATH = '/users/auth/confirm-email/'
const CONFIRM_LINK = '/confirm-email?token=signed-token'

describe('ConfirmEmailPage', () => {
  it('changes the email only once confirmed, then signs this tab out', async () => {
    const confirm = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(http.post(apiUrl(CONFIRM_PATH), confirm))
    const { user, queryClient } = renderRoute(CONFIRM_LINK, { signedInAs: buildCurrentUser() })

    expect(
      await screen.findByRole('heading', { name: 'Confirm your new email' }),
    ).toBeInTheDocument()
    expect(confirm).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Confirm new email' }))

    expect(await screen.findByRole('heading', { name: 'Email changed' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login')
    expect(await confirm.mock.calls[0][0].request.json()).toEqual({ token: 'signed-token' })
    // The API signed the account out everywhere; this tab stops pretending otherwise.
    expect(queryClient.getQueryData(authKeys.currentUser)).toBeNull()
  })

  it("shows the API's reason when the change is refused", async () => {
    server.use(
      http.post(apiUrl(CONFIRM_PATH), () =>
        HttpResponse.json({ detail: 'This email address is already in use.' }, { status: 400 }),
      ),
    )
    const { user } = renderRoute(CONFIRM_LINK)

    await user.click(await screen.findByRole('button', { name: 'Confirm new email' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This email address is already in use.',
    )
    expect(screen.queryByRole('heading', { name: 'Email changed' })).not.toBeInTheDocument()
  })

  it('rejects a link missing its token', () => {
    renderRoute('/confirm-email')

    expect(screen.getByRole('heading', { name: 'Invalid confirmation link' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Confirm new email' })).not.toBeInTheDocument()
  })
})
