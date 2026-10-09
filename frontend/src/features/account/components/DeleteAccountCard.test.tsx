import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { buildCurrentUser } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const DELETE_PATH = '/users/me/delete/'

async function openDialog(user: ReturnType<typeof renderRoute>['user']) {
  await user.click(screen.getByRole('button', { name: 'Delete my account' }))
  return within(await screen.findByRole('form', { name: 'Delete your account' }))
}

describe('DeleteAccountCard', () => {
  it('deletes the account with the password, then signs out', async () => {
    const deleteAccount = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(http.post(apiUrl(DELETE_PATH), deleteAccount))
    const { router, user } = renderRoute('/settings/account', { signedInAs: buildCurrentUser() })
    const dialog = await openDialog(user)

    await user.type(dialog.getByLabelText('Current password'), 'Old-Pass-123!')
    await user.click(dialog.getByRole('button', { name: 'Delete my account' }))

    expect(await screen.findByText('Your account has been deleted.')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(await deleteAccount.mock.calls[0][0].request.json()).toEqual({
      current_password: 'Old-Pass-123!',
    })
  })

  it("shows the API's reason, such as being the only Owner of something", async () => {
    server.use(
      http.post(apiUrl(DELETE_PATH), () =>
        HttpResponse.json(
          { detail: "You're the only Owner of 0 project(s) and 1 document(s)." },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderRoute('/settings/account', { signedInAs: buildCurrentUser() })
    const dialog = await openDialog(user)

    await user.type(dialog.getByLabelText('Current password'), 'Old-Pass-123!')
    await user.click(dialog.getByRole('button', { name: 'Delete my account' }))

    expect(await dialog.findByText(/only Owner of 0 project/)).toBeInTheDocument()
  })

  it('asks for the password before sending anything, and forgets it when closed', async () => {
    const { user } = renderRoute('/settings/account', { signedInAs: buildCurrentUser() })
    let dialog = await openDialog(user)

    await user.type(dialog.getByLabelText('Current password'), 'typed')
    await user.clear(dialog.getByLabelText('Current password'))
    await user.click(dialog.getByRole('button', { name: 'Delete my account' }))
    expect(await dialog.findByText('Enter your current password.')).toBeInTheDocument()

    await user.type(dialog.getByLabelText('Current password'), 'half-typed')
    await user.keyboard('{Escape}')
    dialog = await openDialog(user)
    expect(dialog.getByLabelText('Current password')).toHaveValue('')
  })
})
