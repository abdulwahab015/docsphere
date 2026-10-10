import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { buildCurrentUser, buildOrganization, buildOrganizationSummary } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const DELETE_PATH = '/organizations/delete/'
const admin = buildCurrentUser({ org_role: 'ADMIN' })

async function openDialog(user: ReturnType<typeof renderRoute>['user']) {
  await user.click(await screen.findByRole('button', { name: 'Delete organization' }))
  return within(await screen.findByRole('form', { name: 'Delete Acme' }))
}

describe('DeleteOrganizationCard', () => {
  beforeEach(() => {
    server.use(
      http.get(apiUrl('/organizations/profile/'), () => HttpResponse.json(buildOrganization())),
    )
  })

  it("deletes once the name is typed, then shows what's left of the organization", async () => {
    const deleteOrganization = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(
      http.post(apiUrl(DELETE_PATH), deleteOrganization),
      http.get(apiUrl('/users/me/'), () =>
        HttpResponse.json({
          ...admin,
          organization: buildOrganizationSummary({
            deletion_scheduled_for: '2026-11-08T10:00:00Z',
          }),
        }),
      ),
    )
    const { user } = renderRoute('/settings/organization', { signedInAs: admin })
    const dialog = await openDialog(user)
    const submit = dialog.getByRole('button', { name: 'Delete organization' })

    await user.type(dialog.getByLabelText('Type "Acme" to confirm'), 'Acm')
    expect(submit).toBeDisabled()
    await user.type(dialog.getByLabelText('Type "Acme" to confirm'), 'e')
    await user.click(submit)

    expect(await screen.findByRole('heading', { name: 'Organization deleted' })).toBeInTheDocument()
    expect(await deleteOrganization.mock.calls[0][0].request.json()).toEqual({ name: 'Acme' })
  })

  it("shows the API's reason under the field", async () => {
    server.use(
      http.post(apiUrl(DELETE_PATH), () =>
        HttpResponse.json({ name: ["Type the organization's name exactly."] }, { status: 400 }),
      ),
    )
    const { user } = renderRoute('/settings/organization', { signedInAs: admin })
    const dialog = await openDialog(user)

    await user.type(dialog.getByLabelText('Type "Acme" to confirm'), 'Acme')
    await user.click(dialog.getByRole('button', { name: 'Delete organization' }))

    expect(await dialog.findByText("Type the organization's name exactly.")).toBeInTheDocument()
  })

  it('forgets what was typed when the dialog closes', async () => {
    const { user } = renderRoute('/settings/organization', { signedInAs: admin })
    let dialog = await openDialog(user)

    await user.type(dialog.getByLabelText('Type "Acme" to confirm'), 'Acme')
    await user.keyboard('{Escape}')
    dialog = await openDialog(user)

    expect(dialog.getByLabelText('Type "Acme" to confirm')).toHaveValue('')
  })
})
