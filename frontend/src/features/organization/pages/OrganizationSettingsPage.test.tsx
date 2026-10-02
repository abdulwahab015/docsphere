import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { buildCurrentUser, buildOrganization } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const PROFILE_PATH = '/organizations/profile/'
const SETTINGS_URL = '/settings/organization'

const admin = buildCurrentUser({ org_role: 'ADMIN' })

function serveOrganization(organization = buildOrganization()) {
  server.use(http.get(apiUrl(PROFILE_PATH), () => HttpResponse.json(organization)))
}

describe('OrganizationSettingsPage', () => {
  it("shows the organization's name, and leaves billing to the Billing page", async () => {
    serveOrganization()
    renderRoute(SETTINGS_URL, { signedInAs: admin })

    expect(await screen.findByLabelText('Organization name')).toHaveValue('Acme')
    expect(screen.queryByLabelText('Billing email')).not.toBeInTheDocument()
  })

  it('saves changes, confirms, and updates the name shown in the app', async () => {
    serveOrganization()
    const update = spyResolver(() => HttpResponse.json(buildOrganization({ name: 'Acme Corp' })))
    server.use(
      http.patch(apiUrl(PROFILE_PATH), update),
      http.get(apiUrl('/users/me/'), () =>
        HttpResponse.json({
          ...admin,
          organization: { ...admin.organization, name: 'Acme Corp' },
        }),
      ),
    )
    const { user } = renderRoute(SETTINGS_URL, { signedInAs: admin })
    const nameInput = await screen.findByLabelText('Organization name')

    await user.clear(nameInput)
    await user.type(nameInput, 'Acme Corp')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByText('Organization details saved.')).toBeInTheDocument()
    expect(await update.mock.calls[0][0].request.json()).toEqual({ name: 'Acme Corp' })
    expect(await screen.findByRole('button', { name: 'Account menu' })).toHaveTextContent(
      'Admin · Acme Corp',
    )
  })

  it("shows the server's errors under the name", async () => {
    serveOrganization()
    server.use(
      http.patch(apiUrl(PROFILE_PATH), () =>
        HttpResponse.json(
          { name: ['Ensure this field has no more than 100 characters.'] },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderRoute(SETTINGS_URL, { signedInAs: admin })

    await user.type(await screen.findByLabelText('Organization name'), ' Corp')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByLabelText('Organization name')).toHaveAccessibleDescription(
      expect.stringContaining('Ensure this field has no more than 100 characters.'),
    )
  })

  it('offers a retry when loading fails', async () => {
    server.use(http.get(apiUrl(PROFILE_PATH), () => HttpResponse.json({}, { status: 500 })))
    const { user } = renderRoute(SETTINGS_URL, { signedInAs: admin })

    expect(await screen.findByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument()

    serveOrganization()
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByLabelText('Organization name')).toHaveValue('Acme')
  })

  it("tells members they don't have access, without calling the API", () => {
    renderRoute(SETTINGS_URL, { signedInAs: buildCurrentUser({ org_role: 'MEMBER' }) })

    expect(screen.getByRole('heading', { name: "You don't have access" })).toBeInTheDocument()
  })

  it('shows "no access" if the API refuses', async () => {
    server.use(
      http.get(apiUrl(PROFILE_PATH), () =>
        HttpResponse.json({ detail: 'Not allowed.' }, { status: 403 }),
      ),
    )
    renderRoute(SETTINGS_URL, { signedInAs: admin })

    expect(
      await screen.findByRole('heading', { name: "You don't have access" }),
    ).toBeInTheDocument()
  })
})
