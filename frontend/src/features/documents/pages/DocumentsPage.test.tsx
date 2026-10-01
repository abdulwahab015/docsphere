import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { Document } from '@/api/types'
import { buildCurrentUser, buildDocument } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const DOCUMENTS_PATH = '/documents/'
const member = buildCurrentUser({ org_role: 'MEMBER' })

function serveDocuments(documents: Document[]) {
  const list = spyResolver(({ request }) => {
    const search = new URL(request.url).searchParams.get('search') ?? ''
    const results = documents.filter((document) => document.title.includes(search))
    return HttpResponse.json({ count: results.length, results })
  })
  server.use(http.get(apiUrl(DOCUMENTS_PATH), list))
  return list
}

describe('DocumentsPage', () => {
  describe('listing', () => {
    it('shows every document the user can open, marking personal ones', async () => {
      serveDocuments([
        buildDocument({ id: 1, title: 'Findings', project: 7, access_level: 'EDITOR' }),
        buildDocument({ id: 2, title: 'Journal', project: null, visibility: 'PUBLIC' }),
      ])
      renderRoute('/documents', { signedInAs: member })

      const journal = (await screen.findByRole('link', { name: 'Journal' })).closest('tr')!
      expect(within(journal).getByText('Personal')).toBeInTheDocument()
      expect(within(journal).getByText('Public')).toBeInTheDocument()
      const findings = screen.getByRole('link', { name: 'Findings' }).closest('tr')!
      expect(within(findings).queryByText('Personal')).not.toBeInTheDocument()
      expect(within(findings).getByText('Editor')).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Findings' })).toHaveAttribute('href', '/documents/1')
      expect(document.title).toBe('Documents · DocSphere')
    })

    it('searches by title', async () => {
      const list = serveDocuments([
        buildDocument({ id: 1, title: 'Findings' }),
        buildDocument({ id: 2, title: 'Journal' }),
      ])
      const { user } = renderRoute('/documents', { signedInAs: member })
      await screen.findByRole('link', { name: 'Journal' })

      await user.type(screen.getByRole('searchbox', { name: 'Search documents' }), 'Find')

      expect(await screen.findByText('Showing 1–1 of 1')).toBeInTheDocument()
      const lastUrl = new URL(list.mock.calls.at(-1)![0].request.url)
      expect(lastUrl.searchParams.get('search')).toBe('Find')
    })

    it('gives every member the create and trash controls', async () => {
      serveDocuments([])
      renderRoute('/documents', { signedInAs: member })

      expect(await screen.findByRole('button', { name: 'New document' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Trash' })).toHaveAttribute(
        'href',
        '/documents/trash',
      )
    })

    it('suggests how to start when there are no documents', async () => {
      serveDocuments([])
      renderRoute('/documents', { signedInAs: member })

      expect(await screen.findByRole('heading', { name: 'No documents yet' })).toBeInTheDocument()
    })

    it('explains when a search matches nothing', async () => {
      serveDocuments([buildDocument()])
      renderRoute('/documents?search=zzz', { signedInAs: member })

      expect(await screen.findByRole('heading', { name: 'No matches' })).toBeInTheDocument()
    })

    it('offers a retry when loading fails', async () => {
      server.use(http.get(apiUrl(DOCUMENTS_PATH), () => HttpResponse.json({}, { status: 500 })))
      const { user } = renderRoute('/documents', { signedInAs: member })

      const retry = await screen.findByRole('button', { name: 'Try again' })
      serveDocuments([buildDocument()])
      await user.click(retry)

      expect(await screen.findByRole('link', { name: 'Findings' })).toBeInTheDocument()
    })
  })

  describe('creating a personal document', () => {
    it('creates it outside any project and opens it', async () => {
      serveDocuments([])
      const created = buildDocument({ id: 21, title: 'Journal', content: '' })
      const create = spyResolver(() => HttpResponse.json(created, { status: 201 }))
      server.use(
        http.post(apiUrl(DOCUMENTS_PATH), create),
        http.get(apiUrl('/documents/21/'), () => HttpResponse.json(created)),
      )
      const { router, user } = renderRoute('/documents', { signedInAs: member })

      await user.click(await screen.findByRole('button', { name: 'New document' }))
      const dialog = await screen.findByRole('dialog', { name: 'New document' })
      expect(within(dialog).getByText(/A personal document/)).toBeInTheDocument()
      await user.type(within(dialog).getByLabelText('Title'), 'Journal')
      await user.click(within(dialog).getByRole('button', { name: 'Create document' }))

      expect(await screen.findByText('Created "Journal".')).toBeInTheDocument()
      expect(await create.mock.calls[0][0].request.json()).toEqual({
        title: 'Journal',
        content: '',
        visibility: 'PRIVATE',
        project: null,
      })
      expect(router.state.location.pathname).toBe('/documents/21')
    })

    it('requires a title, and starts fresh when reopened', async () => {
      serveDocuments([])
      const { user } = renderRoute('/documents', { signedInAs: member })

      await user.click(await screen.findByRole('button', { name: 'New document' }))
      let dialog = await screen.findByRole('dialog', { name: 'New document' })
      await user.click(within(dialog).getByRole('radio', { name: 'Public' }))
      await user.click(within(dialog).getByRole('button', { name: 'Create document' }))
      expect(await within(dialog).findByText('Enter a title.')).toBeInTheDocument()

      await user.keyboard('{Escape}')
      await user.click(screen.getByRole('button', { name: 'New document' }))
      dialog = await screen.findByRole('dialog', { name: 'New document' })
      expect(within(dialog).getByRole('radio', { name: 'Private' })).toBeChecked()
    })

    it("shows the server's reason when creation is refused", async () => {
      serveDocuments([])
      server.use(
        http.post(apiUrl(DOCUMENTS_PATH), () =>
          HttpResponse.json(
            { detail: 'You must belong to an organization to create a document.' },
            { status: 400 },
          ),
        ),
      )
      const { user } = renderRoute('/documents', { signedInAs: member })

      await user.click(await screen.findByRole('button', { name: 'New document' }))
      const dialog = await screen.findByRole('dialog', { name: 'New document' })
      await user.type(within(dialog).getByLabelText('Title'), 'Journal')
      await user.click(within(dialog).getByRole('button', { name: 'Create document' }))

      expect(await within(dialog).findByRole('alert')).toHaveTextContent(
        'You must belong to an organization to create a document.',
      )
    })
  })
})
