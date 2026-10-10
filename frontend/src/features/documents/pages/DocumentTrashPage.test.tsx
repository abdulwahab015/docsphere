import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { Document } from '@/api/types'
import { buildCurrentUser, buildDocument } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const TRASH_URL = '/documents/trash'
// Not admin-only: every member has a trash for the documents they own.
const member = buildCurrentUser({ org_role: 'MEMBER' })

function serveTrash(documents: Document[]) {
  server.use(
    http.get(apiUrl('/documents/trash/'), () =>
      HttpResponse.json({ count: documents.length, results: documents }),
    ),
  )
}

describe('DocumentTrashPage', () => {
  it("lists the member's own deleted documents", async () => {
    serveTrash([buildDocument({ id: 1, title: 'Old memo' })])
    renderRoute(TRASH_URL, { signedInAs: member })

    expect(await screen.findByRole('cell', { name: 'Old memo' })).toBeInTheDocument()
    expect(document.title).toBe('Document trash · DocSphere')
  })

  it('restores a document', async () => {
    serveTrash([buildDocument({ id: 1, title: 'Old memo' })])
    const restore = spyResolver(() =>
      HttpResponse.json(buildDocument({ id: 1, title: 'Old memo' })),
    )
    server.use(http.post(apiUrl('/documents/1/restore/'), restore))
    const { user } = renderRoute(TRASH_URL, { signedInAs: member })
    const restoreButton = await screen.findByRole('button', { name: 'Restore Old memo' })

    serveTrash([])
    await user.click(restoreButton)

    expect(await screen.findByText('Restored "Old memo".')).toBeInTheDocument()
    expect(restore).toHaveBeenCalledTimes(1)
    expect(await screen.findByRole('heading', { name: 'The trash is empty' })).toBeInTheDocument()
  })

  it('reports a failed restore', async () => {
    serveTrash([buildDocument({ id: 1, title: 'Old memo' })])
    server.use(
      http.post(apiUrl('/documents/1/restore/'), () => HttpResponse.json({}, { status: 403 })),
    )
    const { user } = renderRoute(TRASH_URL, { signedInAs: member })

    await user.click(await screen.findByRole('button', { name: 'Restore Old memo' }))

    expect(await screen.findByText('Couldn\'t restore "Old memo".')).toBeInTheDocument()
  })

  it("explains why a document in a trashed project can't be restored yet", async () => {
    serveTrash([buildDocument({ id: 1, title: 'Old memo', project: 7 })])
    server.use(
      http.post(apiUrl('/documents/1/restore/'), () =>
        HttpResponse.json(
          {
            detail:
              "This document's project is in the trash. Ask an organization admin to restore the project first.",
          },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderRoute(TRASH_URL, { signedInAs: member })

    await user.click(await screen.findByRole('button', { name: 'Restore Old memo' }))

    expect(await screen.findByText(/restore the project first/)).toBeInTheDocument()
  })

  it('says when the trash is empty', async () => {
    serveTrash([])
    renderRoute(TRASH_URL, { signedInAs: member })

    expect(await screen.findByRole('heading', { name: 'The trash is empty' })).toBeInTheDocument()
  })

  it('offers a retry when loading fails', async () => {
    server.use(http.get(apiUrl('/documents/trash/'), () => HttpResponse.json({}, { status: 500 })))
    const { user } = renderRoute(TRASH_URL, { signedInAs: member })

    const retry = await screen.findByRole('button', { name: 'Try again' })
    serveTrash([])
    await user.click(retry)

    expect(await screen.findByRole('heading', { name: 'The trash is empty' })).toBeInTheDocument()
  })
})
