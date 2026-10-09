import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { buildCurrentUser, buildOrganization } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const admin = buildCurrentUser({ org_role: 'ADMIN' })

describe('ExportDataCard', () => {
  beforeEach(() => {
    server.use(
      http.get(apiUrl('/organizations/profile/'), () => HttpResponse.json(buildOrganization())),
    )
  })

  it('asks for an export and says a link is on its way', async () => {
    const requestExport = spyResolver(() => new HttpResponse(null, { status: 202 }))
    server.use(http.post(apiUrl('/organizations/exports/'), requestExport))
    const { user } = renderRoute('/settings/organization', { signedInAs: admin })

    await user.click(await screen.findByRole('button', { name: 'Email me an export' }))

    expect(await screen.findByText(/We'll email you a link when it's ready/)).toBeInTheDocument()
    expect(requestExport).toHaveBeenCalledTimes(1)
  })

  it("says when one is already on its way, in the API's words", async () => {
    server.use(
      http.post(apiUrl('/organizations/exports/'), () =>
        HttpResponse.json(
          { detail: 'An export of this organization is already being prepared.' },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderRoute('/settings/organization', { signedInAs: admin })

    await user.click(await screen.findByRole('button', { name: 'Email me an export' }))

    expect(await screen.findByText(/already being prepared/)).toBeInTheDocument()
  })

  it("says when the day's limit is reached", async () => {
    server.use(
      http.post(apiUrl('/organizations/exports/'), () =>
        HttpResponse.json({ detail: 'Request was throttled.' }, { status: 429 }),
      ),
    )
    const { user } = renderRoute('/settings/organization', { signedInAs: admin })

    await user.click(await screen.findByRole('button', { name: 'Email me an export' }))

    expect(await screen.findByText(/as many exports as it can today/)).toBeInTheDocument()
  })

  it('reports a failure', async () => {
    server.use(
      http.post(apiUrl('/organizations/exports/'), () => HttpResponse.json({}, { status: 500 })),
    )
    const { user } = renderRoute('/settings/organization', { signedInAs: admin })

    await user.click(await screen.findByRole('button', { name: 'Email me an export' }))

    expect(await screen.findByText("Couldn't start the export. Try again.")).toBeInTheDocument()
  })
})
