import { fireEvent, screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { Document, DocumentVersionDetail } from '@/api/types'
import { documentKeys } from '@/features/documents/query-keys'
import {
  buildCurrentUser,
  buildDocument,
  buildDocumentVersion,
  buildProject,
} from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const DOCUMENT_PATH = '/documents/11/'
const DOCUMENT_URL = '/documents/11'
const signedInAs = buildCurrentUser()

function serveDocument(document: Document) {
  const fetchDocument = spyResolver(() => HttpResponse.json(document))
  server.use(http.get(apiUrl(DOCUMENT_PATH), fetchDocument))
  return fetchDocument
}

function serveSave(saved: Document) {
  const save = spyResolver(() => HttpResponse.json(saved))
  server.use(http.patch(apiUrl(DOCUMENT_PATH), save))
  return save
}

async function contentBox() {
  return screen.findByLabelText('Content')
}

describe('DocumentPage', () => {
  describe('editing (Editor and above)', () => {
    it('saves the title and content', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      const save = serveSave(
        buildDocument({ access_level: 'EDITOR', title: 'Findings v2', content: 'Second draft.' }),
      )
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })

      const saveButton = await screen.findByRole('button', { name: 'Save' })
      expect(saveButton).toBeDisabled()
      await user.clear(screen.getByLabelText('Title'))
      await user.type(screen.getByLabelText('Title'), 'Findings v2')
      await user.clear(await contentBox())
      await user.type(await contentBox(), 'Second draft.')
      expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
      await user.click(saveButton)

      expect(await screen.findByText('Document saved.')).toBeInTheDocument()
      expect(await save.mock.calls[0][0].request.json()).toEqual({
        title: 'Findings v2',
        content: 'Second draft.',
        // The revision the edit started from.
        base_revision: 1,
      })
      expect(
        await screen.findByRole('heading', { level: 1, name: 'Findings v2' }),
      ).toBeInTheDocument()
      expect(screen.getByText(/^Saved /)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
    })

    it('saves with Ctrl+S while typing', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      const save = serveSave(
        buildDocument({ access_level: 'EDITOR', content: 'First draft. More' }),
      )
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })

      await user.type(await contentBox(), ' More')
      await user.keyboard('{Control>}s{/Control}')

      expect(await screen.findByText('Document saved.')).toBeInTheDocument()
      expect(save).toHaveBeenCalledTimes(1)
    })

    it('keeps what is being typed when the document is refreshed in the background', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      const { queryClient, user } = renderRoute(DOCUMENT_URL, { signedInAs })

      await user.type(await contentBox(), ' unsaved words')
      const refetched = serveDocument(
        buildDocument({ access_level: 'EDITOR', content: 'Changed elsewhere.', revision: 2 }),
      )
      await queryClient.invalidateQueries({ queryKey: documentKeys.detail(11) })

      expect(refetched).toHaveBeenCalled()
      expect(await contentBox()).toHaveValue('First draft. unsaved words')

      // Still based on the revision the typing started from, so the API can
      // tell the save would overwrite the newer one.
      const save = serveSave(buildDocument({ access_level: 'EDITOR', revision: 3 }))
      await user.click(screen.getByRole('button', { name: 'Save' }))
      await vi.waitFor(() => expect(save).toHaveBeenCalled())
      expect(await save.mock.calls[0][0].request.json()).toMatchObject({ base_revision: 1 })
    })

    it('shows server errors on the title', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      server.use(
        http.patch(apiUrl(DOCUMENT_PATH), () =>
          HttpResponse.json(
            { title: ['Ensure this field has no more than 100 characters.'] },
            { status: 400 },
          ),
        ),
      )
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })

      await user.type(await screen.findByLabelText('Title'), '!')
      await user.click(screen.getByRole('button', { name: 'Save' }))

      expect(await screen.findByLabelText('Title')).toHaveAccessibleDescription(
        'Ensure this field has no more than 100 characters.',
      )
    })
  })

  describe('when someone else saved first', () => {
    const theirs = buildDocument({
      access_level: 'EDITOR',
      content: 'Their text.',
      revision: 2,
      modified: '2026-09-16T10:30:00Z',
    })

    function refuseSaves() {
      const refusal = spyResolver(() =>
        HttpResponse.json(
          { detail: 'Someone else saved this document.', code: 'edit_conflict', document: theirs },
          { status: 409 },
        ),
      )
      server.use(http.patch(apiUrl(DOCUMENT_PATH), refusal))
      return refusal
    }

    async function typeAndSave(user: ReturnType<typeof renderRoute>['user']) {
      await user.clear(await contentBox())
      await user.type(await contentBox(), 'My text.')
      await user.click(screen.getByRole('button', { name: 'Save' }))
      return screen.findByRole('alert')
    }

    it('keeps what was typed and explains why it was not saved', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      refuseSaves()
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })

      const alert = await typeAndSave(user)

      expect(alert).toHaveTextContent('Someone else saved this document')
      expect(alert).toHaveTextContent("your changes haven't been saved")
      expect(await contentBox()).toHaveValue('My text.')
      expect(screen.queryByText('Document saved.')).not.toBeInTheDocument()
    })

    it('replaces their version with this one on request', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      refuseSaves()
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const alert = await typeAndSave(user)

      const overwrite = serveSave(
        buildDocument({ access_level: 'EDITOR', content: 'My text.', revision: 3 }),
      )
      await user.click(within(alert).getByRole('button', { name: 'Overwrite with mine' }))

      expect(await screen.findByText('Document saved.')).toBeInTheDocument()
      // Based on their revision now: replacing it was the point.
      expect(await overwrite.mock.calls[0][0].request.json()).toEqual({
        title: 'Findings',
        content: 'My text.',
        base_revision: 2,
      })
      expect(screen.queryByText('Someone else saved this document')).not.toBeInTheDocument()
      expect(await contentBox()).toHaveValue('My text.')
    })

    it('shows their version instead, discarding this one, on request', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      refuseSaves()
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const alert = await typeAndSave(user)

      await user.click(within(alert).getByRole('button', { name: 'Reload theirs' }))

      expect(await contentBox()).toHaveValue('Their text.')
      expect(screen.queryByText('Someone else saved this document')).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()

      // The next edit starts from their revision.
      const save = serveSave(buildDocument({ access_level: 'EDITOR', revision: 3 }))
      await user.type(await contentBox(), ' Mine too.')
      await user.click(screen.getByRole('button', { name: 'Save' }))
      await vi.waitFor(() => expect(save).toHaveBeenCalled())
      expect(await save.mock.calls[0][0].request.json()).toMatchObject({ base_revision: 2 })
    })
  })

  describe('leaving with unsaved changes', () => {
    it('asks first, and stays when the user cancels', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      const { router, user } = renderRoute(DOCUMENT_URL, { signedInAs })

      await user.type(await contentBox(), ' unsaved')
      await user.click(
        within(screen.getByRole('navigation', { name: 'Main' })).getByRole('link', {
          name: 'Documents',
        }),
      )

      const confirm = await screen.findByRole('alertdialog', { name: 'Discard unsaved changes?' })
      await user.click(within(confirm).getByRole('button', { name: 'Cancel' }))

      expect(router.state.location.pathname).toBe(DOCUMENT_URL)
      expect(await contentBox()).toHaveValue('First draft. unsaved')
    })

    it('leaves once the user discards the changes', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      const { router, user } = renderRoute(DOCUMENT_URL, { signedInAs })

      await user.type(await contentBox(), ' unsaved')
      await user.click(
        within(screen.getByRole('navigation', { name: 'Main' })).getByRole('link', {
          name: 'Documents',
        }),
      )
      await user.click(await screen.findByRole('button', { name: 'Discard changes' }))

      expect(router.state.location.pathname).toBe('/documents')
    })

    it('lets the browser warn before the tab is closed', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      await contentBox()

      expect(fireEvent(window, new Event('beforeunload', { cancelable: true }))).toBe(true)

      await user.type(await contentBox(), ' unsaved')

      expect(fireEvent(window, new Event('beforeunload', { cancelable: true }))).toBe(false)
    })

    it("doesn't ask when nothing changed", async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      const { router, user } = renderRoute(DOCUMENT_URL, { signedInAs })

      await contentBox()
      await user.click(
        within(screen.getByRole('navigation', { name: 'Main' })).getByRole('link', {
          name: 'Documents',
        }),
      )

      expect(router.state.location.pathname).toBe('/documents')
    })
  })

  describe('version history (Editor and above)', () => {
    // Revision 3 is the document as it is now.
    const current = buildDocument({
      access_level: 'EDITOR',
      title: 'Findings v3',
      content: 'Third draft.',
      revision: 3,
    })
    const versions = [
      buildDocumentVersion({
        revision: 3,
        title: 'Findings v3',
        content: 'Third draft.',
        created_by_name: 'Grace Hopper',
        created: '2026-09-03T09:00:00Z',
      }),
      buildDocumentVersion({ revision: 2, title: 'Findings v2', content: 'Second draft.' }),
      buildDocumentVersion({ revision: 1, title: 'Findings', content: 'First draft.' }),
    ]

    function serveVersions(served: DocumentVersionDetail[] = versions) {
      server.use(
        http.get(apiUrl(`${DOCUMENT_PATH}versions/`), () =>
          HttpResponse.json({
            count: served.length,
            results: served.map(({ content: _content, ...listed }) => listed),
          }),
        ),
        http.get(apiUrl(`${DOCUMENT_PATH}versions/:revision/`), ({ params }) =>
          HttpResponse.json(served.find((version) => version.revision === Number(params.revision))),
        ),
      )
    }

    async function openHistory(user: ReturnType<typeof renderRoute>['user']) {
      await user.click(await screen.findByRole('button', { name: 'History' }))
      return screen.findByRole('dialog', { name: 'Version history' })
    }

    it('lists the versions newest first, with who saved each and the current one marked', async () => {
      serveDocument(current)
      serveVersions()
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })

      const dialog = await openHistory(user)

      const list = await within(dialog).findByRole('list', { name: 'Versions' })
      const entries = within(list).getAllByRole('button')
      expect(entries.map((entry) => entry.textContent)).toEqual([
        expect.stringMatching(/^Version 3Current.*Findings v3.*Grace Hopper/),
        expect.stringMatching(/^Version 2Findings v2/),
        expect.stringMatching(/^Version 1Findings/),
      ])
    })

    it('opens an old version to read, and goes back to the list', async () => {
      serveDocument(current)
      serveVersions()
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const dialog = await openHistory(user)

      await user.click(await within(dialog).findByRole('button', { name: /^Version 1/ }))

      const version = await screen.findByRole('article', { name: 'Version 1' })
      expect(within(version).getByRole('heading', { name: 'Findings' })).toBeInTheDocument()
      expect(within(version).getByText('First draft.')).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'All versions' }))
      expect(await screen.findByRole('list', { name: 'Versions' })).toBeInTheDocument()
    })

    it('says when a version had no text', async () => {
      serveDocument(current)
      serveVersions([versions[0], buildDocumentVersion({ revision: 1, content: '' })])
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const dialog = await openHistory(user)

      await user.click(await within(dialog).findByRole('button', { name: /^Version 1/ }))

      expect(await screen.findByRole('article', { name: 'Version 1' })).toHaveTextContent(
        'No text.',
      )
    })

    it("doesn't offer to restore the current version", async () => {
      serveDocument(current)
      serveVersions()
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const dialog = await openHistory(user)

      await user.click(await within(dialog).findByRole('button', { name: /^Version 3/ }))

      expect(await screen.findByText('This is the current version.')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Restore this version' })).not.toBeInTheDocument()
    })

    it('restores an old version, after confirming, as a save based on the current revision', async () => {
      serveDocument(current)
      serveVersions()
      const save = serveSave({
        ...current,
        title: 'Findings',
        content: 'First draft.',
        revision: 4,
      })
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const dialog = await openHistory(user)
      await user.click(await within(dialog).findByRole('button', { name: /^Version 1/ }))

      await user.click(await screen.findByRole('button', { name: 'Restore this version' }))
      const confirm = await screen.findByRole('alertdialog', { name: 'Restore version 1?' })
      await user.click(within(confirm).getByRole('button', { name: 'Restore' }))

      expect(await screen.findByText('Restored version 1.')).toBeInTheDocument()
      expect(await save.mock.calls[0][0].request.json()).toEqual({
        title: 'Findings',
        content: 'First draft.',
        base_revision: 3,
      })
      expect(screen.queryByRole('dialog', { name: 'Version history' })).not.toBeInTheDocument()
      expect(await screen.findByRole('heading', { level: 1, name: 'Findings' })).toBeInTheDocument()
    })

    it('refuses to restore over a save made since the history was opened', async () => {
      serveDocument(current)
      serveVersions()
      server.use(
        http.patch(apiUrl(DOCUMENT_PATH), () =>
          HttpResponse.json(
            {
              detail: 'Someone else saved this document.',
              code: 'edit_conflict',
              document: { ...current, content: 'Their text.', revision: 4 },
            },
            { status: 409 },
          ),
        ),
      )
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const dialog = await openHistory(user)
      await user.click(await within(dialog).findByRole('button', { name: /^Version 1/ }))

      await user.click(await screen.findByRole('button', { name: 'Restore this version' }))
      await user.click(await screen.findByRole('button', { name: 'Restore' }))

      expect(
        await screen.findByText(
          'Someone saved this document since you opened its history. Check the newest version before restoring.',
        ),
      ).toBeInTheDocument()
    })

    it('offers a retry when the history or a version fails to load', async () => {
      serveDocument(current)
      server.use(
        http.get(apiUrl(`${DOCUMENT_PATH}versions/`), () => HttpResponse.json({}, { status: 500 })),
        http.get(apiUrl(`${DOCUMENT_PATH}versions/:revision/`), () =>
          HttpResponse.json({}, { status: 500 }),
        ),
      )
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      await openHistory(user)

      const retryList = await screen.findByRole('button', { name: 'Try again' })
      serveVersions()
      await user.click(retryList)
      expect(await screen.findByRole('list', { name: 'Versions' })).toBeInTheDocument()

      server.use(
        http.get(apiUrl(`${DOCUMENT_PATH}versions/:revision/`), () =>
          HttpResponse.json({}, { status: 500 }),
        ),
      )
      await user.click(screen.getByRole('button', { name: /^Version 1/ }))
      const retryVersion = await screen.findByRole('button', { name: 'Try again' })
      serveVersions()
      await user.click(retryVersion)
      expect(await screen.findByRole('article', { name: 'Version 1' })).toBeInTheDocument()
    })

    it('reports any other failed restore', async () => {
      serveDocument(current)
      serveVersions()
      server.use(http.patch(apiUrl(DOCUMENT_PATH), () => HttpResponse.json({}, { status: 500 })))
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const dialog = await openHistory(user)
      await user.click(await within(dialog).findByRole('button', { name: /^Version 1/ }))

      await user.click(await screen.findByRole('button', { name: 'Restore this version' }))
      await user.click(await screen.findByRole('button', { name: 'Restore' }))

      expect(
        await screen.findByText("Couldn't restore this version. Try again."),
      ).toBeInTheDocument()
    })
  })

  describe('reading (Viewer)', () => {
    it('shows the content without editing controls', async () => {
      serveDocument(buildDocument({ access_level: 'VIEWER', visibility: 'PUBLIC' }))
      renderRoute(DOCUMENT_URL, { signedInAs })

      expect(await screen.findByText('First draft.')).toBeInTheDocument()
      expect(screen.getByText(/Its owner can give you edit access/)).toBeInTheDocument()
      expect(screen.queryByLabelText('Content')).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
      expect(
        screen.queryByRole('button', { name: /Make (public|private)/ }),
      ).not.toBeInTheDocument()
      // Past versions may hold text that was removed: Viewers see only the current one.
      expect(screen.queryByRole('button', { name: 'History' })).not.toBeInTheDocument()
      expect(document.title).toBe('Findings · DocSphere')
    })

    it('says when the document is empty', async () => {
      serveDocument(buildDocument({ access_level: 'VIEWER', content: null }))
      renderRoute(DOCUMENT_URL, { signedInAs })

      expect(await screen.findByText('This document is empty.')).toBeInTheDocument()
    })
  })

  describe('as the owner', () => {
    it('makes the document public after confirming', async () => {
      serveDocument(buildDocument())
      const save = serveSave(buildDocument({ visibility: 'PUBLIC' }))
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })

      await user.click(await screen.findByRole('button', { name: 'Make public' }))
      const confirm = await screen.findByRole('alertdialog', { name: 'Make this document public?' })
      await user.click(within(confirm).getByRole('button', { name: 'Make public' }))

      expect(await screen.findByText('Document is now public.')).toBeInTheDocument()
      expect(await save.mock.calls[0][0].request.json()).toEqual({ visibility: 'PUBLIC' })
    })

    it('moves the document to the trash after confirming', async () => {
      serveDocument(buildDocument())
      const destroy = spyResolver(() => new HttpResponse(null, { status: 204 }))
      server.use(http.delete(apiUrl(DOCUMENT_PATH), destroy))
      const { router, user } = renderRoute(DOCUMENT_URL, { signedInAs })

      await user.click(await screen.findByRole('button', { name: 'Delete' }))
      const confirm = await screen.findByRole('alertdialog', { name: 'Delete "Findings"?' })
      expect(within(confirm).getByText(/restore it from your document trash/)).toBeInTheDocument()
      await user.click(within(confirm).getByRole('button', { name: 'Delete document' }))

      expect(await screen.findByText('Moved "Findings" to your trash.')).toBeInTheDocument()
      expect(destroy).toHaveBeenCalledTimes(1)
      expect(router.state.location.pathname).toBe('/documents')
    })

    it('reports a failed deletion and stays on the document', async () => {
      serveDocument(buildDocument())
      server.use(http.delete(apiUrl(DOCUMENT_PATH), () => HttpResponse.json({}, { status: 500 })))
      const { router, user } = renderRoute(DOCUMENT_URL, { signedInAs })

      await user.click(await screen.findByRole('button', { name: 'Delete' }))
      await user.click(await screen.findByRole('button', { name: 'Delete document' }))

      expect(await screen.findByText('Couldn\'t delete "Findings".')).toBeInTheDocument()
      expect(router.state.location.pathname).toBe(DOCUMENT_URL)
    })
  })

  describe('its project', () => {
    it('names a personal document as having none', async () => {
      serveDocument(buildDocument({ project: null }))
      renderRoute(DOCUMENT_URL, { signedInAs })

      expect(await screen.findByText('None (personal document)')).toBeInTheDocument()
    })

    it('links to the project when the reader can open it', async () => {
      serveDocument(buildDocument({ project: 7 }))
      server.use(http.get(apiUrl('/projects/7/'), () => HttpResponse.json(buildProject())))
      renderRoute(DOCUMENT_URL, { signedInAs })

      expect(await screen.findByRole('link', { name: 'Roadmap' })).toHaveAttribute(
        'href',
        '/projects/7',
      )
    })

    it("doesn't reveal a project the reader can't open", async () => {
      serveDocument(buildDocument({ project: 7 }))
      server.use(
        http.get(apiUrl('/projects/7/'), () =>
          HttpResponse.json({ detail: 'No Project matches the given query.' }, { status: 404 }),
        ),
      )
      renderRoute(DOCUMENT_URL, { signedInAs })

      expect(await screen.findByText("A project you can't open")).toBeInTheDocument()
      expect(screen.queryByRole('link', { name: 'Roadmap' })).not.toBeInTheDocument()
    })
  })

  describe('when the document is unavailable', () => {
    it('shows "not found" for a document the user cannot see', async () => {
      server.use(http.get(apiUrl(DOCUMENT_PATH), () => HttpResponse.json({}, { status: 404 })))
      renderRoute(DOCUMENT_URL, { signedInAs })

      expect(await screen.findByRole('heading', { name: 'Not found' })).toBeInTheDocument()
    })

    it('shows "not found" for a malformed link without asking the API', () => {
      renderRoute('/documents/abc', { signedInAs })

      expect(screen.getByRole('heading', { name: 'Not found' })).toBeInTheDocument()
    })

    it('offers a retry when loading fails', async () => {
      server.use(http.get(apiUrl(DOCUMENT_PATH), () => HttpResponse.json({}, { status: 500 })))
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })

      const retry = await screen.findByRole('button', { name: 'Try again' })
      serveDocument(buildDocument())
      await user.click(retry)

      expect(await screen.findByRole('heading', { level: 1, name: 'Findings' })).toBeInTheDocument()
    })
  })
})
