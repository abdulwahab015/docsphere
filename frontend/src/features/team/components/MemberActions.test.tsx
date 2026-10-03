import { screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'

import type { SoleOwnership, UserDetail } from '@/api/types'
import { formatDate } from '@/lib/format'
import { buildCurrentUser, buildSoleOwnership, buildUserDetail } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const admin = buildCurrentUser({ org_role: 'ADMIN' })
const ADA = buildUserDetail({ id: 1, email: 'ada@example.com', org_role: 'ADMIN' })
const GRACE = buildUserDetail()

function serveRoster(members: UserDetail[]) {
  const list = spyResolver(() => HttpResponse.json({ count: members.length, results: members }))
  server.use(http.get(apiUrl('/users/'), list))
  return list
}

function serveSoleOwnership(ownership: SoleOwnership = buildSoleOwnership()) {
  server.use(http.get(apiUrl('/projects/sole-ownership/2/'), () => HttpResponse.json(ownership)))
}

function rowFor(email: string) {
  return within(screen.getByRole('row', { name: new RegExp(email) }))
}

async function chooseAction(user: UserEvent, email: string, action: string) {
  await user.click(await screen.findByRole('button', { name: `Actions for ${email}` }))
  await user.click(await screen.findByRole('menuitem', { name: action }))
  return screen.findByRole('alertdialog')
}

describe('MemberActions', () => {
  it("shows admins each member's role and join date, with no actions on their own row", async () => {
    serveRoster([ADA, GRACE])
    renderRoute('/people', { signedInAs: admin })

    await screen.findByText('grace@example.com')
    expect(screen.getByRole('tab', { name: 'Members' })).toHaveAttribute('aria-selected', 'true')
    expect(rowFor('grace@example.com').getByText('Member')).toBeInTheDocument()
    expect(rowFor('grace@example.com').getByText(formatDate(GRACE.created))).toBeInTheDocument()
    expect(rowFor('ada@example.com').getByText('Admin')).toBeInTheDocument()
    expect(rowFor('ada@example.com').getByText('You')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Actions for ada@example.com' }),
    ).not.toBeInTheDocument()
  })

  it('makes a member an admin after confirming', async () => {
    const list = serveRoster([ADA, GRACE])
    const changeRole = spyResolver(() => HttpResponse.json({ ...GRACE, org_role: 'ADMIN' }))
    server.use(http.patch(apiUrl('/users/2/role/'), changeRole))
    const { user } = renderRoute('/people', { signedInAs: admin })

    const confirm = await chooseAction(user, 'grace@example.com', 'Make admin')
    expect(confirm).toHaveAccessibleName('Make grace@example.com an admin?')
    await user.click(within(confirm).getByRole('button', { name: 'Make admin' }))

    expect(await screen.findByText('grace@example.com is now an admin.')).toBeInTheDocument()
    expect(await changeRole.mock.calls[0][0].request.json()).toEqual({ org_role: 'ADMIN' })
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
  })

  it('makes an admin a member after confirming', async () => {
    const lin = buildUserDetail({ id: 3, email: 'lin@example.com', org_role: 'ADMIN' })
    serveRoster([ADA, lin])
    const changeRole = spyResolver(() => HttpResponse.json({ ...lin, org_role: 'MEMBER' }))
    server.use(http.patch(apiUrl('/users/3/role/'), changeRole))
    const { user } = renderRoute('/people', { signedInAs: admin })

    const confirm = await chooseAction(user, 'lin@example.com', 'Make member')
    await user.click(within(confirm).getByRole('button', { name: 'Make member' }))

    expect(await screen.findByText('lin@example.com is now a member.')).toBeInTheDocument()
    expect(await changeRole.mock.calls[0][0].request.json()).toEqual({ org_role: 'MEMBER' })
  })

  it('deactivates a member after confirming', async () => {
    const list = serveRoster([ADA, GRACE])
    serveSoleOwnership()
    const deactivate = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(http.delete(apiUrl('/users/2/deactivate/'), deactivate))
    const { user } = renderRoute('/people', { signedInAs: admin })

    const confirm = await chooseAction(user, 'grace@example.com', 'Deactivate')
    expect(within(confirm).getByText(/They'll be signed out/)).toBeInTheDocument()
    expect(within(confirm).queryByText(/only Owner/)).not.toBeInTheDocument()
    await user.click(within(confirm).getByRole('button', { name: 'Deactivate' }))

    expect(await screen.findByText('Deactivated grace@example.com.')).toBeInTheDocument()
    expect(deactivate).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
  })

  it('warns when the member is the only Owner of projects or documents', async () => {
    serveRoster([ADA, GRACE])
    serveSoleOwnership(buildSoleOwnership({ projects: 2, documents: 1 }))
    const { user } = renderRoute('/people', { signedInAs: admin })

    const confirm = await chooseAction(user, 'grace@example.com', 'Deactivate')

    expect(
      await within(confirm).findByText(
        "They're the only Owner of 2 projects and 1 document. Nobody can change who has access to those until they're reactivated.",
      ),
    ).toBeInTheDocument()
  })

  it('names only what they own alone', async () => {
    serveRoster([ADA, GRACE])
    serveSoleOwnership(buildSoleOwnership({ documents: 3 }))
    const { user } = renderRoute('/people', { signedInAs: admin })

    const confirm = await chooseAction(user, 'grace@example.com', 'Deactivate')

    expect(await within(confirm).findByText(/only Owner of 3 documents\./)).toBeInTheDocument()
  })

  it('still lets the admin deactivate when the ownership check fails', async () => {
    serveRoster([ADA, GRACE])
    const ownership = spyResolver(() => HttpResponse.json({}, { status: 500 }))
    server.use(http.get(apiUrl('/projects/sole-ownership/2/'), ownership))
    const deactivate = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(http.delete(apiUrl('/users/2/deactivate/'), deactivate))
    const { user } = renderRoute('/people', { signedInAs: admin })

    const confirm = await chooseAction(user, 'grace@example.com', 'Deactivate')
    await waitFor(() => expect(ownership).toHaveBeenCalled())
    await user.click(within(confirm).getByRole('button', { name: 'Deactivate' }))

    expect(await screen.findByText('Deactivated grace@example.com.')).toBeInTheDocument()
  })

  it('changes nothing when the admin cancels', async () => {
    serveRoster([ADA, GRACE])
    serveSoleOwnership()
    const deactivate = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(http.delete(apiUrl('/users/2/deactivate/'), deactivate))
    const { user } = renderRoute('/people', { signedInAs: admin })

    const confirm = await chooseAction(user, 'grace@example.com', 'Deactivate')
    await user.click(within(confirm).getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(deactivate).not.toHaveBeenCalled()
  })

  it("reports the API's reason when a change is refused", async () => {
    serveRoster([ADA, GRACE])
    server.use(
      http.patch(apiUrl('/users/2/role/'), () =>
        HttpResponse.json({ detail: 'You cannot change your own role.' }, { status: 400 }),
      ),
    )
    const { user } = renderRoute('/people', { signedInAs: admin })

    const confirm = await chooseAction(user, 'grace@example.com', 'Make admin')
    await user.click(within(confirm).getByRole('button', { name: 'Make admin' }))

    expect(await screen.findByText('You cannot change your own role.')).toBeInTheDocument()
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })

  it('reports a failed deactivation', async () => {
    serveRoster([ADA, GRACE])
    serveSoleOwnership()
    server.use(
      http.delete(apiUrl('/users/2/deactivate/'), () => HttpResponse.json({}, { status: 500 })),
    )
    const { user } = renderRoute('/people', { signedInAs: admin })

    const confirm = await chooseAction(user, 'grace@example.com', 'Deactivate')
    await user.click(within(confirm).getByRole('button', { name: 'Deactivate' }))

    expect(await screen.findByText("Couldn't deactivate grace@example.com.")).toBeInTheDocument()
  })
})
