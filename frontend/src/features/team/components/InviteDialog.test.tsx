import { screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'

import { buildCurrentUser, buildInvitation } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const INVITATIONS_PATH = '/users/invitations/'
const admin = buildCurrentUser({ org_role: 'ADMIN' })

function serveInvitationList() {
  const list = spyResolver(() => HttpResponse.json({ count: 0, results: [] }))
  server.use(http.get(apiUrl(INVITATIONS_PATH), list))
  return list
}

async function openInviteDialog(user: UserEvent) {
  await user.click(await screen.findByRole('button', { name: 'Invite' }))
  return within(await screen.findByRole('dialog', { name: 'Invite someone' }))
}

describe('InviteDialog', () => {
  it('sends an invitation and refreshes the list of invitations', async () => {
    const list = serveInvitationList()
    const create = spyResolver(() => HttpResponse.json(buildInvitation(), { status: 201 }))
    server.use(http.post(apiUrl(INVITATIONS_PATH), create))
    const { user } = renderRoute('/people?tab=invitations', { signedInAs: admin })

    const dialog = await openInviteDialog(user)
    expect(dialog.getByText(/join Acme as a member/)).toBeInTheDocument()
    await user.type(dialog.getByLabelText('Email'), 'newcomer@example.com')
    await user.click(dialog.getByRole('button', { name: 'Send invitation' }))

    expect(await screen.findByText('Invitation sent to newcomer@example.com.')).toBeInTheDocument()
    expect(await create.mock.calls[0][0].request.json()).toEqual({
      email: 'newcomer@example.com',
    })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
  })

  it('checks the address before sending', async () => {
    serveInvitationList()
    const { user } = renderRoute('/people?tab=invitations', { signedInAs: admin })

    const dialog = await openInviteDialog(user)
    await user.type(dialog.getByLabelText('Email'), 'not-an-email')
    await user.click(dialog.getByRole('button', { name: 'Send invitation' }))

    expect(dialog.getByLabelText('Email')).toHaveAccessibleDescription(
      'Enter a valid email address.',
    )
  })

  it("shows the API's reason under the address", async () => {
    serveInvitationList()
    server.use(
      http.post(apiUrl(INVITATIONS_PATH), () =>
        HttpResponse.json({ email: ['A user with this email already exists.'] }, { status: 400 }),
      ),
    )
    const { user } = renderRoute('/people?tab=invitations', { signedInAs: admin })

    const dialog = await openInviteDialog(user)
    await user.type(dialog.getByLabelText('Email'), 'grace@example.com')
    await user.click(dialog.getByRole('button', { name: 'Send invitation' }))

    await waitFor(() =>
      expect(dialog.getByLabelText('Email')).toHaveAccessibleDescription(
        'A user with this email already exists.',
      ),
    )
  })

  it('shows a refusal about the organization above the form', async () => {
    serveInvitationList()
    server.use(
      http.post(apiUrl(INVITATIONS_PATH), () =>
        HttpResponse.json(
          { non_field_errors: ['This organization has too many pending invitations.'] },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderRoute('/people?tab=invitations', { signedInAs: admin })

    const dialog = await openInviteDialog(user)
    await user.type(dialog.getByLabelText('Email'), 'one-more@example.com')
    await user.click(dialog.getByRole('button', { name: 'Send invitation' }))

    expect(
      await dialog.findByText('This organization has too many pending invitations.'),
    ).toBeInTheDocument()
  })

  it('starts empty when reopened', async () => {
    serveInvitationList()
    const { user } = renderRoute('/people?tab=invitations', { signedInAs: admin })

    const dialog = await openInviteDialog(user)
    await user.type(dialog.getByLabelText('Email'), 'draft@example.com')
    await user.keyboard('{Escape}')
    const reopened = await openInviteDialog(user)

    expect(reopened.getByLabelText('Email')).toHaveValue('')
  })

  it('is offered only to admins', async () => {
    server.use(http.get(apiUrl('/users/'), () => HttpResponse.json({ count: 0, results: [] })))
    renderRoute('/people', { signedInAs: buildCurrentUser() })

    expect(await screen.findByText('No one here yet')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Invite' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Upload a list' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab')).not.toBeInTheDocument()
  })
})
