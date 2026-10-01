import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { Invitation } from '@/api/types'
import { buildCurrentUser, buildInvitation } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, heldResponse, server, spyResolver } from '@/test/server'

const INVITATIONS_PATH = '/users/invitations/'
const INVITATIONS_URL = '/people?tab=invitations'
const admin = buildCurrentUser({ org_role: 'ADMIN' })
const PENDING = buildInvitation()
const EXPIRED = buildInvitation({ id: 42, email: 'late@example.com', status: 'EXPIRED' })
const ACCEPTED = buildInvitation({ id: 43, email: 'joined@example.com', status: 'ACCEPTED' })
const REVOKED = buildInvitation({
  id: 44,
  email: 'withdrawn@example.com',
  status: 'REVOKED',
  invited_by_email: null,
})

function serveInvitations(invitations: Invitation[], { count = invitations.length } = {}) {
  const list = spyResolver(() => HttpResponse.json({ count, results: invitations }))
  server.use(http.get(apiUrl(INVITATIONS_PATH), list))
  return list
}

function rowFor(email: string) {
  return within(screen.getByRole('row', { name: new RegExp(email) }))
}

describe('InvitationList', () => {
  it('lists invitations, offering resend and revoke only where they apply', async () => {
    serveInvitations([PENDING, EXPIRED, ACCEPTED, REVOKED])
    renderRoute(INVITATIONS_URL, { signedInAs: admin })

    await screen.findByText('newcomer@example.com')
    expect(screen.getByRole('tab', { name: 'Invitations' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    const pending = rowFor('newcomer@example.com')
    expect(pending.getByText('Pending')).toBeInTheDocument()
    expect(pending.getByText('ada@example.com')).toBeInTheDocument()
    expect(pending.getByRole('button', { name: 'Resend' })).toBeInTheDocument()
    expect(pending.getByRole('button', { name: 'Revoke' })).toBeInTheDocument()
    const expired = rowFor('late@example.com')
    expect(expired.getByText('Expired')).toBeInTheDocument()
    expect(expired.getByRole('button', { name: 'Resend' })).toBeInTheDocument()
    expect(expired.queryByRole('button', { name: 'Revoke' })).not.toBeInTheDocument()
    expect(rowFor('joined@example.com').queryByRole('button')).not.toBeInTheDocument()
    const revoked = rowFor('withdrawn@example.com')
    expect(revoked.getByText('Revoked')).toBeInTheDocument()
    expect(revoked.getByText('—')).toBeInTheDocument()
    expect(revoked.queryByRole('button')).not.toBeInTheDocument()
  })

  it('resends an invitation with a new link', async () => {
    const list = serveInvitations([EXPIRED])
    const resend = heldResponse(() => HttpResponse.json({ ...EXPIRED, status: 'PENDING' }))
    server.use(http.post(apiUrl('/users/invitations/42/resend/'), resend.resolver))
    const { user } = renderRoute(INVITATIONS_URL, { signedInAs: admin })

    const button = await screen.findByRole('button', { name: 'Resend' })
    await user.click(button)
    expect(button).toBeDisabled()
    resend.release()

    expect(
      await screen.findByText(
        'Sent a new invitation to late@example.com. The earlier link no longer works.',
      ),
    ).toBeInTheDocument()
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
  })

  it("reports the API's reason when a resend is refused", async () => {
    serveInvitations([EXPIRED])
    server.use(
      http.post(apiUrl('/users/invitations/42/resend/'), () =>
        HttpResponse.json(
          { detail: 'This email already has a pending invitation.' },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderRoute(INVITATIONS_URL, { signedInAs: admin })

    await user.click(await screen.findByRole('button', { name: 'Resend' }))

    expect(
      await screen.findByText('This email already has a pending invitation.'),
    ).toBeInTheDocument()
  })

  it('revokes an invitation after confirming', async () => {
    serveInvitations([PENDING])
    const revoke = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(http.delete(apiUrl('/users/invitations/41/'), revoke))
    const { user } = renderRoute(INVITATIONS_URL, { signedInAs: admin })

    await user.click(await screen.findByRole('button', { name: 'Revoke' }))
    const confirm = await screen.findByRole('alertdialog', {
      name: 'Revoke the invitation to newcomer@example.com?',
    })
    expect(within(confirm).getByText(/The link in their email will stop working/)).toBeVisible()
    await user.click(within(confirm).getByRole('button', { name: 'Revoke' }))

    expect(
      await screen.findByText('Revoked the invitation to newcomer@example.com.'),
    ).toBeInTheDocument()
    expect(revoke).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })

  it('keeps the invitation when the admin cancels', async () => {
    serveInvitations([PENDING])
    const revoke = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(http.delete(apiUrl('/users/invitations/41/'), revoke))
    const { user } = renderRoute(INVITATIONS_URL, { signedInAs: admin })

    await user.click(await screen.findByRole('button', { name: 'Revoke' }))
    await user.click(
      within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Cancel' }),
    )

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(revoke).not.toHaveBeenCalled()
  })

  it('reports a failed revoke', async () => {
    serveInvitations([PENDING])
    server.use(
      http.delete(apiUrl('/users/invitations/41/'), () => HttpResponse.json({}, { status: 500 })),
    )
    const { user } = renderRoute(INVITATIONS_URL, { signedInAs: admin })

    await user.click(await screen.findByRole('button', { name: 'Revoke' }))
    await user.click(
      within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Revoke' }),
    )

    expect(
      await screen.findByText("Couldn't revoke the invitation to newcomer@example.com."),
    ).toBeInTheDocument()
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })

  it('says when nobody has been invited yet', async () => {
    serveInvitations([])
    renderRoute(INVITATIONS_URL, { signedInAs: admin })

    expect(await screen.findByText('No invitations yet')).toBeInTheDocument()
  })

  it('pages through a long list', async () => {
    const list = serveInvitations([PENDING], { count: 25 })
    const { router, user } = renderRoute(INVITATIONS_URL, { signedInAs: admin })

    await user.click(await screen.findByRole('button', { name: 'Next' }))

    await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
    expect(router.state.location.search).toBe('?tab=invitations&page=2')
  })

  it('offers a retry when loading fails', async () => {
    server.use(http.get(apiUrl(INVITATIONS_PATH), () => HttpResponse.json({}, { status: 500 })))
    const { user } = renderRoute(INVITATIONS_URL, { signedInAs: admin })

    const retry = await screen.findByRole('button', { name: 'Try again' })
    serveInvitations([PENDING])
    await user.click(retry)

    expect(await screen.findByText('newcomer@example.com')).toBeInTheDocument()
  })
})
