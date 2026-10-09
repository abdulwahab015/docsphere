import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { buildCurrentUser, buildOrganizationSummary } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const deleted = buildOrganizationSummary({ deletion_scheduled_for: '2026-11-08T10:00:00Z' })

describe('OrganizationDeletedScreen', () => {
  it('tells an admin when it goes and lets them restore it', async () => {
    const admin = buildCurrentUser({ org_role: 'ADMIN', organization: deleted })
    const restore = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(
      http.post(apiUrl('/organizations/delete/cancel/'), restore),
      http.get(apiUrl('/users/me/'), () =>
        HttpResponse.json({ ...admin, organization: buildOrganizationSummary() }),
      ),
    )
    const { user } = renderRoute('/projects', { signedInAs: admin })

    expect(screen.getByRole('heading', { name: 'Organization deleted' })).toBeInTheDocument()
    expect(screen.getByText(/removed for good on Nov 8, 2026/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Restore organization' }))

    expect(await screen.findByText('Restored Acme.')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Projects' })).toBeInTheDocument()
    expect(restore).toHaveBeenCalledTimes(1)
  })

  it('reports a failed restore', async () => {
    server.use(
      http.post(apiUrl('/organizations/delete/cancel/'), () =>
        HttpResponse.json({ detail: "This organization isn't deleted." }, { status: 400 }),
      ),
    )
    const { user } = renderRoute('/projects', {
      signedInAs: buildCurrentUser({ org_role: 'ADMIN', organization: deleted }),
    })

    await user.click(screen.getByRole('button', { name: 'Restore organization' }))

    expect(await screen.findByText("This organization isn't deleted.")).toBeInTheDocument()
  })

  it('tells a member to ask an admin, with no way to restore it', () => {
    renderRoute('/projects', {
      signedInAs: buildCurrentUser({ org_role: 'MEMBER', organization: deleted }),
    })

    expect(screen.getByText(/Ask an admin if this is a mistake/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Restore organization' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument()
  })
})
