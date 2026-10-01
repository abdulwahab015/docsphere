import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { Project } from '@/api/types'
import { buildCurrentUser, buildProject } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const TRASH_URL = '/projects/trash'
const admin = buildCurrentUser({ org_role: 'ADMIN' })

function serveTrash(projects: Project[]) {
  server.use(
    http.get(apiUrl('/projects/trash/'), () =>
      HttpResponse.json({ count: projects.length, results: projects }),
    ),
  )
}

describe('ProjectTrashPage', () => {
  it("lists deleted projects, including private ones the admin can't open", async () => {
    serveTrash([
      buildProject({ id: 1, name: 'Old launch', access_level: 'OWNER' }),
      buildProject({ id: 2, name: 'Secret', access_level: null }),
    ])
    renderRoute(TRASH_URL, { signedInAs: admin })

    const secret = (await screen.findByRole('cell', { name: 'Secret' })).closest('tr')!
    expect(within(secret).getByText('No access')).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Old launch' })).toBeInTheDocument()
    expect(screen.getByText('Showing 1–2 of 2')).toBeInTheDocument()
  })

  it('restores a project', async () => {
    serveTrash([buildProject({ id: 1, name: 'Old launch' })])
    const restore = spyResolver(() =>
      HttpResponse.json(buildProject({ id: 1, name: 'Old launch' })),
    )
    server.use(http.post(apiUrl('/projects/1/restore/'), restore))
    const { user } = renderRoute(TRASH_URL, { signedInAs: admin })
    const restoreButton = await screen.findByRole('button', { name: 'Restore Old launch' })

    // After the restore, the trash no longer holds it.
    serveTrash([])
    await user.click(restoreButton)

    expect(await screen.findByText('Restored "Old launch".')).toBeInTheDocument()
    expect(restore).toHaveBeenCalledTimes(1)
    expect(await screen.findByRole('heading', { name: 'The trash is empty' })).toBeInTheDocument()
  })

  it('reports a failed restore', async () => {
    serveTrash([buildProject({ id: 1, name: 'Old launch' })])
    server.use(
      http.post(apiUrl('/projects/1/restore/'), () => HttpResponse.json({}, { status: 500 })),
    )
    const { user } = renderRoute(TRASH_URL, { signedInAs: admin })

    await user.click(await screen.findByRole('button', { name: 'Restore Old launch' }))

    expect(await screen.findByText('Couldn\'t restore "Old launch".')).toBeInTheDocument()
  })

  it('says when the trash is empty', async () => {
    serveTrash([])
    renderRoute(TRASH_URL, { signedInAs: admin })

    expect(await screen.findByRole('heading', { name: 'The trash is empty' })).toBeInTheDocument()
  })

  it('offers a retry when loading fails', async () => {
    server.use(http.get(apiUrl('/projects/trash/'), () => HttpResponse.json({}, { status: 500 })))
    const { user } = renderRoute(TRASH_URL, { signedInAs: admin })

    const retry = await screen.findByRole('button', { name: 'Try again' })
    serveTrash([])
    await user.click(retry)

    expect(await screen.findByRole('heading', { name: 'The trash is empty' })).toBeInTheDocument()
  })

  it('is admin-only', () => {
    renderRoute(TRASH_URL, { signedInAs: buildCurrentUser({ org_role: 'MEMBER' }) })

    expect(screen.getByRole('heading', { name: "You don't have access" })).toBeInTheDocument()
  })
})
