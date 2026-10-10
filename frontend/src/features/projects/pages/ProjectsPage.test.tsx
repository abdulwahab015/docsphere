import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { buildCurrentUser, buildProject } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const PROJECTS_PATH = '/projects/'
const admin = buildCurrentUser({ org_role: 'ADMIN' })
const member = buildCurrentUser({ org_role: 'MEMBER' })

function serveProjects(projects = [buildProject()]) {
  const list = spyResolver(({ request }) => {
    const search = new URL(request.url).searchParams.get('search') ?? ''
    const results = projects.filter((project) => project.name.includes(search))
    return HttpResponse.json({ count: results.length, results })
  })
  server.use(http.get(apiUrl(PROJECTS_PATH), list))
  return list
}

describe('ProjectsPage', () => {
  describe('listing', () => {
    it("shows each project with its visibility and the user's access", async () => {
      serveProjects([
        buildProject({ id: 1, name: 'Handbook', visibility: 'PUBLIC', access_level: 'VIEWER' }),
        buildProject({ id: 2, name: 'Roadmap', visibility: 'PRIVATE', access_level: 'EDITOR' }),
      ])
      renderRoute('/projects', { signedInAs: member })

      const handbook = (await screen.findByRole('link', { name: 'Handbook' })).closest('tr')!
      expect(within(handbook).getByText('Public')).toBeInTheDocument()
      expect(within(handbook).getByText('Viewer')).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Handbook' })).toHaveAttribute('href', '/projects/1')
      const roadmap = screen.getByRole('link', { name: 'Roadmap' }).closest('tr')!
      expect(within(roadmap).getByText('Private')).toBeInTheDocument()
      expect(within(roadmap).getByText('Editor')).toBeInTheDocument()
    })

    it('searches by name', async () => {
      const list = serveProjects([
        buildProject({ id: 1, name: 'Handbook' }),
        buildProject({ id: 2, name: 'Roadmap' }),
      ])
      const { user } = renderRoute('/projects', { signedInAs: member })
      await screen.findByRole('link', { name: 'Roadmap' })

      await user.type(screen.getByRole('searchbox', { name: 'Search projects' }), 'Hand')

      expect(await screen.findByText('Showing 1–1 of 1')).toBeInTheDocument()
      expect(screen.queryByRole('link', { name: 'Roadmap' })).not.toBeInTheDocument()
      const lastUrl = new URL(list.mock.calls.at(-1)![0].request.url)
      expect(lastUrl.searchParams.get('search')).toBe('Hand')
    })

    it('gives admins the create and trash controls', async () => {
      serveProjects()
      renderRoute('/projects', { signedInAs: admin })

      expect(await screen.findByRole('button', { name: 'New project' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Trash' })).toHaveAttribute('href', '/projects/trash')
    })

    it('hides them from members, who cannot create or restore projects', async () => {
      serveProjects()
      renderRoute('/projects', { signedInAs: member })

      await screen.findByRole('link', { name: 'Roadmap' })
      expect(screen.queryByRole('button', { name: 'New project' })).not.toBeInTheDocument()
      expect(screen.queryByRole('link', { name: 'Trash' })).not.toBeInTheDocument()
    })

    it('invites an admin to create the first project', async () => {
      serveProjects([])
      renderRoute('/projects', { signedInAs: admin })

      expect(await screen.findByRole('heading', { name: 'No projects yet' })).toBeInTheDocument()
      expect(screen.getByText(/Create the first one/)).toBeInTheDocument()
    })

    it('tells a member how projects will reach them', async () => {
      serveProjects([])
      renderRoute('/projects', { signedInAs: member })

      expect(await screen.findByText(/once someone shares one with you/)).toBeInTheDocument()
    })

    it('explains when a search matches nothing', async () => {
      serveProjects()
      renderRoute('/projects?search=zzz', { signedInAs: member })

      expect(await screen.findByRole('heading', { name: 'No matches' })).toBeInTheDocument()
    })

    it('offers a retry when loading fails', async () => {
      server.use(http.get(apiUrl(PROJECTS_PATH), () => HttpResponse.json({}, { status: 500 })))
      const { user } = renderRoute('/projects', { signedInAs: member })

      const retry = await screen.findByRole('button', { name: 'Try again' })
      serveProjects()
      await user.click(retry)

      expect(await screen.findByRole('link', { name: 'Roadmap' })).toBeInTheDocument()
    })
  })

  describe('creating a project', () => {
    it('creates it with the chosen visibility and opens it', async () => {
      serveProjects([])
      const created = buildProject({ id: 42, name: 'Launch', visibility: 'PUBLIC' })
      const create = spyResolver(() => HttpResponse.json(created, { status: 201 }))
      server.use(http.post(apiUrl(PROJECTS_PATH), create))
      const { router, user } = renderRoute('/projects', { signedInAs: admin })

      await user.click(await screen.findByRole('button', { name: 'New project' }))
      const dialog = await screen.findByRole('dialog', { name: 'New project' })
      await user.type(within(dialog).getByLabelText('Name'), '  Launch  ')
      await user.type(within(dialog).getByLabelText('Description (optional)'), 'Q4 launch plan')
      await user.click(within(dialog).getByRole('radio', { name: 'Public' }))
      await user.click(within(dialog).getByRole('button', { name: 'Create project' }))

      expect(await screen.findByText('Created "Launch".')).toBeInTheDocument()
      expect(await create.mock.calls[0][0].request.json()).toEqual({
        name: 'Launch',
        description: 'Q4 launch plan',
        visibility: 'PUBLIC',
      })
      expect(router.state.location.pathname).toBe('/projects/42')
      expect(await screen.findByRole('heading', { level: 1, name: 'Launch' })).toBeInTheDocument()
    })

    it('defaults to private and sends no description when left blank', async () => {
      serveProjects([])
      const create = spyResolver(() =>
        HttpResponse.json(buildProject({ id: 43, name: 'Quiet' }), { status: 201 }),
      )
      server.use(http.post(apiUrl(PROJECTS_PATH), create))
      const { user } = renderRoute('/projects', { signedInAs: admin })

      await user.click(await screen.findByRole('button', { name: 'New project' }))
      const dialog = await screen.findByRole('dialog', { name: 'New project' })
      expect(within(dialog).getByRole('radio', { name: 'Private' })).toBeChecked()
      await user.type(within(dialog).getByLabelText('Name'), 'Quiet')
      await user.click(within(dialog).getByRole('button', { name: 'Create project' }))

      await screen.findByText('Created "Quiet".')
      expect(await create.mock.calls[0][0].request.json()).toEqual({
        name: 'Quiet',
        description: null,
        visibility: 'PRIVATE',
      })
    })

    it('shows a name clash under the name field', async () => {
      serveProjects([])
      server.use(
        http.post(apiUrl(PROJECTS_PATH), () =>
          HttpResponse.json(
            { name: ['A project with this name already exists in your organization.'] },
            { status: 400 },
          ),
        ),
      )
      const { user } = renderRoute('/projects', { signedInAs: admin })

      await user.click(await screen.findByRole('button', { name: 'New project' }))
      const dialog = await screen.findByRole('dialog', { name: 'New project' })
      await user.type(within(dialog).getByLabelText('Name'), 'Roadmap')
      await user.click(within(dialog).getByRole('button', { name: 'Create project' }))

      expect(await within(dialog).findByLabelText('Name')).toHaveAccessibleDescription(
        'A project with this name already exists in your organization.',
      )
    })

    it('requires a name, and starts fresh when reopened', async () => {
      serveProjects([])
      const create = spyResolver(() => HttpResponse.json(buildProject(), { status: 201 }))
      server.use(http.post(apiUrl(PROJECTS_PATH), create))
      const { user } = renderRoute('/projects', { signedInAs: admin })

      await user.click(await screen.findByRole('button', { name: 'New project' }))
      let dialog = await screen.findByRole('dialog', { name: 'New project' })
      await user.type(within(dialog).getByLabelText('Description (optional)'), 'Draft')
      await user.click(within(dialog).getByRole('button', { name: 'Create project' }))
      expect(await within(dialog).findByText('Enter a project name.')).toBeInTheDocument()
      expect(create).not.toHaveBeenCalled()

      await user.keyboard('{Escape}')
      await user.click(screen.getByRole('button', { name: 'New project' }))
      dialog = await screen.findByRole('dialog', { name: 'New project' })
      expect(within(dialog).getByLabelText('Description (optional)')).toHaveValue('')
    })
  })
})
