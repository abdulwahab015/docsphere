import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { UserDetail } from '@/api/types'
import { buildCurrentUser, buildUserDetail } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, heldResponse, server, spyResolver } from '@/test/server'

const DEACTIVATED_PATH = '/users/deactivated/'
const DEACTIVATED_URL = '/people?tab=deactivated'
const admin = buildCurrentUser({ org_role: 'ADMIN' })
const LEAVER = buildUserDetail({ id: 5, email: 'leaver@example.com' })

function serveDeactivated(members: UserDetail[]) {
  const list = spyResolver(() => HttpResponse.json({ count: members.length, results: members }))
  server.use(http.get(apiUrl(DEACTIVATED_PATH), list))
  return list
}

describe('DeactivatedMemberList', () => {
  it('reactivates someone, and refreshes the list', async () => {
    const list = serveDeactivated([LEAVER])
    const reactivate = heldResponse(() => HttpResponse.json(LEAVER))
    server.use(http.post(apiUrl('/users/5/reactivate/'), reactivate.resolver))
    const { user } = renderRoute(DEACTIVATED_URL, { signedInAs: admin })

    expect(await screen.findByText('leaver@example.com')).toBeInTheDocument()
    expect(screen.getByText('Member')).toBeInTheDocument()
    const button = screen.getByRole('button', { name: 'Reactivate' })
    await user.click(button)
    expect(button).toBeDisabled()
    reactivate.release()

    expect(
      await screen.findByText('Reactivated leaver@example.com. They can log in again.'),
    ).toBeInTheDocument()
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
  })

  it('names the person, and names them when reactivating', async () => {
    const named = { ...LEAVER, name: 'Lee Leaver' }
    serveDeactivated([named])
    server.use(http.post(apiUrl('/users/5/reactivate/'), () => HttpResponse.json(named)))
    const { user } = renderRoute(DEACTIVATED_URL, { signedInAs: admin })

    expect(await screen.findByText('Lee Leaver')).toBeInTheDocument()
    expect(screen.getByText('leaver@example.com')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Reactivate' }))

    expect(
      await screen.findByText('Reactivated Lee Leaver. They can log in again.'),
    ).toBeInTheDocument()
  })

  it('searches by email', async () => {
    const list = serveDeactivated([LEAVER])
    const { user } = renderRoute(DEACTIVATED_URL, { signedInAs: admin })

    await screen.findByText('leaver@example.com')
    serveDeactivated([])
    await user.type(screen.getByLabelText('Search deactivated people'), 'nobody')

    expect(await screen.findByText('No matches')).toBeInTheDocument()
    expect(list).toHaveBeenCalledTimes(1)
  })

  it('says when no one is deactivated', async () => {
    serveDeactivated([])
    renderRoute(DEACTIVATED_URL, { signedInAs: admin })

    expect(await screen.findByText('No one is deactivated')).toBeInTheDocument()
  })

  it('reports a failed reactivation', async () => {
    serveDeactivated([LEAVER])
    server.use(
      http.post(apiUrl('/users/5/reactivate/'), () => HttpResponse.json({}, { status: 404 })),
    )
    const { user } = renderRoute(DEACTIVATED_URL, { signedInAs: admin })

    await user.click(await screen.findByRole('button', { name: 'Reactivate' }))

    expect(await screen.findByText("Couldn't reactivate leaver@example.com.")).toBeInTheDocument()
  })

  it('offers a retry when loading fails', async () => {
    server.use(http.get(apiUrl(DEACTIVATED_PATH), () => HttpResponse.json({}, { status: 500 })))
    const { user } = renderRoute(DEACTIVATED_URL, { signedInAs: admin })

    const retry = await screen.findByRole('button', { name: 'Try again' })
    serveDeactivated([LEAVER])
    await user.click(retry)

    expect(await screen.findByText('leaver@example.com')).toBeInTheDocument()
  })

  it('opens the first tab for an unknown one, and switching tabs drops the search', async () => {
    server.use(http.get(apiUrl('/users/'), () => HttpResponse.json({ count: 0, results: [] })))
    serveDeactivated([])
    const { router, user } = renderRoute('/people?tab=bogus&search=lea', { signedInAs: admin })

    expect(await screen.findByRole('tab', { name: 'Members' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    await user.click(screen.getByRole('tab', { name: 'Deactivated' }))

    expect(router.state.location.search).toBe('?tab=deactivated')
    expect(await screen.findByText('No one is deactivated')).toBeInTheDocument()
  })
})
