import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { Project } from '@/api/types'
import { buildCurrentUser, buildProject } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const PROJECT_PATH = '/projects/7/'
const signedInAs = buildCurrentUser()

function serveProject(project: Project) {
  server.use(http.get(apiUrl(PROJECT_PATH), () => HttpResponse.json(project)))
}

function serveUpdate(updated: Project) {
  const update = spyResolver(() => HttpResponse.json(updated))
  server.use(http.patch(apiUrl(PROJECT_PATH), update))
  return update
}

describe('ProjectDetailPage', () => {
  describe('as a viewer', () => {
    it('shows the project read-only', async () => {
      serveProject(buildProject({ access_level: 'VIEWER', visibility: 'PUBLIC' }))
      renderRoute('/projects/7', { signedInAs })

      expect(await screen.findByRole('heading', { level: 1, name: 'Roadmap' })).toBeInTheDocument()
      expect(screen.getByText('Where we are headed.')).toBeInTheDocument()
      expect(screen.getByText('Viewer')).toBeInTheDocument()
      expect(screen.getByText('Public')).toBeInTheDocument()
      expect(screen.getByText('Everyone in Acme can view it.')).toBeInTheDocument()
      expect(document.title).toBe('Roadmap · DocSphere')
      expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
      expect(
        screen.queryByRole('button', { name: /Make (public|private)/ }),
      ).not.toBeInTheDocument()
    })

    it('says when there is no description', async () => {
      serveProject(buildProject({ access_level: 'VIEWER', description: null }))
      renderRoute('/projects/7', { signedInAs })

      expect(await screen.findByText('No description.')).toBeInTheDocument()
    })
  })

  describe('as an editor', () => {
    it('edits the name and description, but cannot delete or change visibility', async () => {
      serveProject(buildProject({ access_level: 'EDITOR' }))
      const update = serveUpdate(
        buildProject({ access_level: 'EDITOR', name: 'Roadmap 2027', description: null }),
      )
      const { user } = renderRoute('/projects/7', { signedInAs })

      await user.click(await screen.findByRole('button', { name: 'Edit' }))
      const dialog = await screen.findByRole('dialog', { name: 'Edit project' })
      await user.clear(within(dialog).getByLabelText('Name'))
      await user.type(within(dialog).getByLabelText('Name'), 'Roadmap 2027')
      await user.clear(within(dialog).getByLabelText('Description (optional)'))
      await user.click(within(dialog).getByRole('button', { name: 'Save changes' }))

      expect(await screen.findByText('Project updated.')).toBeInTheDocument()
      expect(await update.mock.calls[0][0].request.json()).toEqual({
        name: 'Roadmap 2027',
        description: null,
      })
      expect(
        await screen.findByRole('heading', { level: 1, name: 'Roadmap 2027' }),
      ).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
      expect(
        screen.queryByRole('button', { name: /Make (public|private)/ }),
      ).not.toBeInTheDocument()
    })

    it('shows a name clash under the name field', async () => {
      serveProject(buildProject({ access_level: 'EDITOR' }))
      server.use(
        http.patch(apiUrl(PROJECT_PATH), () =>
          HttpResponse.json(
            { name: ['A project with this name already exists in your organization.'] },
            { status: 400 },
          ),
        ),
      )
      const { user } = renderRoute('/projects/7', { signedInAs })

      await user.click(await screen.findByRole('button', { name: 'Edit' }))
      const dialog = await screen.findByRole('dialog', { name: 'Edit project' })
      await user.type(within(dialog).getByLabelText('Name'), ' copy')
      await user.click(within(dialog).getByRole('button', { name: 'Save changes' }))

      expect(await within(dialog).findByLabelText('Name')).toHaveAccessibleDescription(
        'A project with this name already exists in your organization.',
      )
    })

    it('discards unsaved edits when the dialog is closed', async () => {
      serveProject(buildProject({ access_level: 'EDITOR' }))
      const { user } = renderRoute('/projects/7', { signedInAs })

      await user.click(await screen.findByRole('button', { name: 'Edit' }))
      let dialog = await screen.findByRole('dialog', { name: 'Edit project' })
      await user.type(within(dialog).getByLabelText('Name'), ' draft')
      await user.keyboard('{Escape}')
      await user.click(screen.getByRole('button', { name: 'Edit' }))

      dialog = await screen.findByRole('dialog', { name: 'Edit project' })
      expect(within(dialog).getByLabelText('Name')).toHaveValue('Roadmap')
    })
  })

  describe('as the owner', () => {
    it('makes a private project public after confirming', async () => {
      serveProject(buildProject({ visibility: 'PRIVATE' }))
      const update = serveUpdate(buildProject({ visibility: 'PUBLIC' }))
      const { user } = renderRoute('/projects/7', { signedInAs })

      await user.click(await screen.findByRole('button', { name: 'Make public' }))
      const confirm = await screen.findByRole('alertdialog', { name: 'Make this project public?' })
      await user.click(within(confirm).getByRole('button', { name: 'Make public' }))

      expect(await screen.findByText('Project is now public.')).toBeInTheDocument()
      expect(await update.mock.calls[0][0].request.json()).toEqual({ visibility: 'PUBLIC' })
      expect(await screen.findByRole('button', { name: 'Make private' })).toBeInTheDocument()
    })

    it('makes a public project private after confirming', async () => {
      serveProject(buildProject({ visibility: 'PUBLIC' }))
      const update = serveUpdate(buildProject({ visibility: 'PRIVATE' }))
      const { user } = renderRoute('/projects/7', { signedInAs })

      await user.click(await screen.findByRole('button', { name: 'Make private' }))
      const confirm = await screen.findByRole('alertdialog', { name: 'Make this project private?' })
      expect(within(confirm).getByText(/will lose access/)).toBeInTheDocument()
      await user.click(within(confirm).getByRole('button', { name: 'Make private' }))

      expect(await screen.findByText('Project is now private.')).toBeInTheDocument()
      expect(await update.mock.calls[0][0].request.json()).toEqual({ visibility: 'PRIVATE' })
    })

    it('reports a failed visibility change', async () => {
      serveProject(buildProject())
      server.use(
        http.patch(apiUrl(PROJECT_PATH), () =>
          HttpResponse.json({ detail: 'Not allowed.' }, { status: 403 }),
        ),
      )
      const { user } = renderRoute('/projects/7', { signedInAs })

      await user.click(await screen.findByRole('button', { name: 'Make public' }))
      const confirm = await screen.findByRole('alertdialog')
      await user.click(within(confirm).getByRole('button', { name: 'Make public' }))

      expect(
        await screen.findByText("Couldn't change the project's visibility."),
      ).toBeInTheDocument()
    })

    it('moves the project to the trash after confirming', async () => {
      serveProject(buildProject())
      const destroy = spyResolver(() => new HttpResponse(null, { status: 204 }))
      server.use(http.delete(apiUrl(PROJECT_PATH), destroy))
      const { router, user } = renderRoute('/projects/7', { signedInAs })

      await user.click(await screen.findByRole('button', { name: 'Delete' }))
      const confirm = await screen.findByRole('alertdialog', { name: 'Delete "Roadmap"?' })
      expect(
        within(confirm).getByText(/along with every document filed under it/),
      ).toBeInTheDocument()
      await user.click(within(confirm).getByRole('button', { name: 'Delete project' }))

      expect(await screen.findByText('Moved "Roadmap" to the trash.')).toBeInTheDocument()
      expect(destroy).toHaveBeenCalledTimes(1)
      expect(router.state.location.pathname).toBe('/projects')
    })

    it('keeps the project when deletion is cancelled', async () => {
      serveProject(buildProject())
      const destroy = spyResolver(() => new HttpResponse(null, { status: 204 }))
      server.use(http.delete(apiUrl(PROJECT_PATH), destroy))
      const { user } = renderRoute('/projects/7', { signedInAs })

      await user.click(await screen.findByRole('button', { name: 'Delete' }))
      await user.click(await screen.findByRole('button', { name: 'Cancel' }))

      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
      expect(destroy).not.toHaveBeenCalled()
    })

    it('reports a failed deletion and stays on the project', async () => {
      serveProject(buildProject())
      server.use(http.delete(apiUrl(PROJECT_PATH), () => HttpResponse.json({}, { status: 500 })))
      const { router, user } = renderRoute('/projects/7', { signedInAs })

      await user.click(await screen.findByRole('button', { name: 'Delete' }))
      await user.click(await screen.findByRole('button', { name: 'Delete project' }))

      expect(await screen.findByText('Couldn\'t delete "Roadmap".')).toBeInTheDocument()
      expect(router.state.location.pathname).toBe('/projects/7')
    })
  })

  describe('when the project is unavailable', () => {
    it('shows "not found" for a project the user cannot see', async () => {
      server.use(
        http.get(apiUrl(PROJECT_PATH), () =>
          HttpResponse.json({ detail: 'No Project matches the given query.' }, { status: 404 }),
        ),
      )
      renderRoute('/projects/7', { signedInAs })

      expect(await screen.findByRole('heading', { name: 'Not found' })).toBeInTheDocument()
    })

    it('shows "not found" for a malformed link without asking the API', () => {
      renderRoute('/projects/not-a-number', { signedInAs })

      expect(screen.getByRole('heading', { name: 'Not found' })).toBeInTheDocument()
    })

    it('offers a retry when loading fails', async () => {
      server.use(http.get(apiUrl(PROJECT_PATH), () => HttpResponse.json({}, { status: 500 })))
      const { user } = renderRoute('/projects/7', { signedInAs })

      const retry = await screen.findByRole('button', { name: 'Try again' })
      serveProject(buildProject())
      await user.click(retry)

      expect(await screen.findByRole('heading', { level: 1, name: 'Roadmap' })).toBeInTheDocument()
    })
  })
})
