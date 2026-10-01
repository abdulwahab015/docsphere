import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { Document, Project } from '@/api/types'
import { buildCurrentUser, buildDocument, buildProject } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const signedInAs = buildCurrentUser()

function serveProject(project: Project) {
  server.use(http.get(apiUrl('/projects/7/'), () => HttpResponse.json(project)))
}

function serveDocuments(documents: Document[]) {
  const list = spyResolver(() => HttpResponse.json({ count: documents.length, results: documents }))
  server.use(http.get(apiUrl('/documents/'), list))
  return list
}

describe("a project's documents", () => {
  it('lists only documents in this project the reader can open, and says why', async () => {
    serveProject(buildProject({ access_level: 'VIEWER' }))
    const list = serveDocuments([buildDocument({ id: 1, title: 'Findings', project: 7 })])
    renderRoute('/projects/7', { signedInAs })

    expect(await screen.findByRole('link', { name: 'Findings' })).toBeInTheDocument()
    expect(
      screen.getByText(/access to this project doesn't include the documents in it/),
    ).toBeInTheDocument()
    const url = new URL(list.mock.calls.at(-1)![0].request.url)
    expect(url.searchParams.get('project')).toBe('7')
  })

  it('lets a project editor add a document to it', async () => {
    serveProject(buildProject({ access_level: 'EDITOR' }))
    serveDocuments([])
    const create = spyResolver(() =>
      HttpResponse.json(buildDocument({ id: 30, title: 'Plan', project: 7 }), { status: 201 }),
    )
    server.use(
      http.post(apiUrl('/documents/'), create),
      http.get(apiUrl('/documents/30/'), () =>
        HttpResponse.json(buildDocument({ id: 30, title: 'Plan', project: 7 })),
      ),
    )
    const { router, user } = renderRoute('/projects/7', { signedInAs })

    await user.click(await screen.findByRole('button', { name: 'New document' }))
    const dialog = await screen.findByRole('dialog', { name: 'New document' })
    expect(within(dialog).getByText(/In Roadmap/)).toBeInTheDocument()
    await user.type(within(dialog).getByLabelText('Title'), 'Plan')
    await user.click(within(dialog).getByRole('button', { name: 'Create document' }))

    expect(await screen.findByText('Created "Plan".')).toBeInTheDocument()
    expect(await create.mock.calls[0][0].request.json()).toMatchObject({
      title: 'Plan',
      project: 7,
    })
    expect(router.state.location.pathname).toBe('/documents/30')
  })

  it("doesn't offer to add documents to a project the reader can only view", async () => {
    serveProject(buildProject({ access_level: 'VIEWER' }))
    serveDocuments([])
    renderRoute('/projects/7', { signedInAs })

    expect(
      await screen.findByRole('heading', { name: 'No documents you can open' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'New document' })).not.toBeInTheDocument()
  })

  it('explains when a search matches nothing', async () => {
    serveProject(buildProject())
    serveDocuments([])
    renderRoute('/projects/7?search=zzz', { signedInAs })

    expect(await screen.findByRole('heading', { name: 'No matches' })).toBeInTheDocument()
  })

  it('offers a retry when loading fails', async () => {
    serveProject(buildProject())
    server.use(http.get(apiUrl('/documents/'), () => HttpResponse.json({}, { status: 500 })))
    const { user } = renderRoute('/projects/7', { signedInAs })

    const retry = await screen.findByRole('button', { name: 'Try again' })
    serveDocuments([buildDocument({ title: 'Findings', project: 7 })])
    await user.click(retry)

    expect(await screen.findByRole('link', { name: 'Findings' })).toBeInTheDocument()
  })
})
