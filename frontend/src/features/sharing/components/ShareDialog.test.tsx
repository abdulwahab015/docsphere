import { screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'

import type { Grant, Project, RosterUser } from '@/api/types'
import { buildCurrentUser, buildDocument, buildGrant, buildProject } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, heldResponse, server, spyResolver } from '@/test/server'

const SHARE_PATH = '/projects/7/share/'
const signedInAs = buildCurrentUser()
const ADA_OWNER = buildGrant()
const GRACE_VIEWER = buildGrant({
  id: 22,
  user: 2,
  user_email: 'grace@example.com',
  access_level: 'VIEWER',
})
const GRACE: RosterUser = { id: 2, email: 'grace@example.com' }
const LIN: RosterUser = { id: 3, email: 'lin@example.com' }

function serveProject(project: Project = buildProject()) {
  server.use(http.get(apiUrl('/projects/7/'), () => HttpResponse.json(project)))
}

/** Serves the list of people with access; `count` can claim more pages. */
function serveGrants(grants: Grant[], { count = grants.length } = {}) {
  const list = spyResolver(() => HttpResponse.json({ count, results: grants }))
  server.use(http.get(apiUrl(SHARE_PATH), list))
  return list
}

function servePeople(people: RosterUser[], { count = people.length } = {}) {
  server.use(http.get(apiUrl('/users/'), () => HttpResponse.json({ count, results: people })))
}

function serveShare(response: () => Response) {
  const share = spyResolver(response)
  server.use(http.post(apiUrl(SHARE_PATH), share))
  return share
}

function serveRevoke(userId: number, response: () => Response) {
  const revoke = spyResolver(response)
  server.use(http.delete(apiUrl(`${SHARE_PATH}${userId}/`), revoke))
  return revoke
}

async function openShareDialog(user: UserEvent) {
  await user.click(await screen.findByRole('button', { name: 'Share' }))
  return within(await screen.findByRole('dialog', { name: /^Share/ }))
}

async function peopleWithAccess(dialog: ReturnType<typeof within>) {
  return within(await dialog.findByRole('list', { name: 'People with access' }))
}

describe('ShareDialog', () => {
  describe('listing people', () => {
    it("lists everyone with access, and says a project's documents aren't shared with it", async () => {
      serveProject()
      serveGrants([ADA_OWNER, GRACE_VIEWER])
      const { user } = renderRoute('/projects/7', { signedInAs })

      const dialog = await openShareDialog(user)
      const people = await peopleWithAccess(dialog)

      expect(dialog.getByText(/Sharing it doesn't share its documents/)).toBeInTheDocument()
      expect(people.getByText('(you)')).toBeInTheDocument()
      expect(people.getByLabelText('Access level for ada@example.com')).toHaveValue('OWNER')
      expect(people.getByLabelText('Access level for grace@example.com')).toHaveValue('VIEWER')
    })

    it('says everyone can already view a public document', async () => {
      server.use(
        http.get(apiUrl('/documents/11/'), () =>
          HttpResponse.json(buildDocument({ visibility: 'PUBLIC' })),
        ),
        http.get(apiUrl('/documents/11/share/'), () =>
          HttpResponse.json({ count: 1, results: [buildGrant()] }),
        ),
      )
      const { user } = renderRoute('/documents/11', { signedInAs })

      const dialog = await openShareDialog(user)

      expect(
        dialog.getByText(/Choose who can open this document.*Everyone in Acme can already view it/),
      ).toBeInTheDocument()
    })

    it('is offered only to Owners', async () => {
      serveProject(buildProject({ access_level: 'EDITOR' }))
      renderRoute('/projects/7', { signedInAs })

      expect(await screen.findByRole('button', { name: 'Edit' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Share' })).not.toBeInTheDocument()
    })

    it('pages through a long list', async () => {
      serveProject()
      const list = serveGrants([ADA_OWNER], { count: 25 })
      const { user } = renderRoute('/projects/7', { signedInAs })

      const dialog = await openShareDialog(user)
      await user.click(await dialog.findByRole('button', { name: 'Next' }))

      await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
      expect(new URL(list.mock.calls[1][0].request.url).searchParams.get('page')).toBe('2')
    })

    it('offers a retry when the list fails to load', async () => {
      serveProject()
      server.use(http.get(apiUrl(SHARE_PATH), () => HttpResponse.json({}, { status: 500 })))
      const { user } = renderRoute('/projects/7', { signedInAs })

      const dialog = await openShareDialog(user)
      serveGrants([ADA_OWNER])
      await user.click(await dialog.findByRole('button', { name: 'Try again' }))

      expect(await peopleWithAccess(dialog)).toBeTruthy()
    })
  })

  describe('adding people', () => {
    it('adds a person at the chosen level', async () => {
      serveProject()
      const list = serveGrants([ADA_OWNER, GRACE_VIEWER])
      servePeople([GRACE, LIN])
      const share = serveShare(() =>
        HttpResponse.json(
          buildGrant({ id: 23, user: 3, user_email: LIN.email, access_level: 'EDITOR' }),
        ),
      )
      const { user } = renderRoute('/projects/7', { signedInAs })

      const dialog = await openShareDialog(user)
      await user.selectOptions(dialog.getByLabelText('Add as'), 'EDITOR')
      expect(dialog.getByText('Editor: Can view and edit.')).toBeInTheDocument()
      await user.type(dialog.getByLabelText('Search people by email'), 'example')
      const matches = within(await dialog.findByRole('list', { name: 'Matching people' }))
      expect(matches.getByText('Has access')).toBeInTheDocument()
      await user.click(matches.getByRole('button', { name: 'Add lin@example.com' }))

      expect(await screen.findByText('lin@example.com now has Editor access.')).toBeInTheDocument()
      expect(await share.mock.calls[0][0].request.json()).toEqual({
        user: 3,
        access_level: 'EDITOR',
      })
      await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
    })

    it('holds off further adds while one is being saved', async () => {
      serveProject()
      serveGrants([ADA_OWNER])
      servePeople([GRACE, LIN])
      const share = heldResponse(() => HttpResponse.json(GRACE_VIEWER))
      server.use(http.post(apiUrl(SHARE_PATH), share.resolver))
      const { user } = renderRoute('/projects/7', { signedInAs })

      const dialog = await openShareDialog(user)
      await user.type(dialog.getByLabelText('Search people by email'), 'example')
      await user.click(await dialog.findByRole('button', { name: 'Add grace@example.com' }))

      expect(dialog.getByRole('button', { name: 'Add grace@example.com' })).toBeDisabled()
      expect(dialog.getByRole('button', { name: 'Add lin@example.com' })).toBeDisabled()
      share.release()
      expect(
        await screen.findByText('grace@example.com now has Viewer access.'),
      ).toBeInTheDocument()
    })

    it('says when nobody matches', async () => {
      serveProject()
      serveGrants([ADA_OWNER])
      servePeople([])
      const { user } = renderRoute('/projects/7', { signedInAs })

      const dialog = await openShareDialog(user)
      await user.type(dialog.getByLabelText('Search people by email'), 'nobody')

      expect(
        await dialog.findByText('No one in your organization matches “nobody”.'),
      ).toBeInTheDocument()
    })

    it('says when there are more matches than it shows', async () => {
      serveProject()
      serveGrants([ADA_OWNER])
      servePeople([LIN], { count: 30 })
      const { user } = renderRoute('/projects/7', { signedInAs })

      const dialog = await openShareDialog(user)
      await user.type(dialog.getByLabelText('Search people by email'), 'example')

      expect(await dialog.findByText(/Showing the first 1 of 30 matches/)).toBeInTheDocument()
    })

    it("reports the API's reason when sharing is refused", async () => {
      serveProject()
      serveGrants([ADA_OWNER])
      servePeople([LIN])
      serveShare(() =>
        HttpResponse.json(
          { user: ['This user does not belong to your organization.'] },
          { status: 400 },
        ),
      )
      const { user } = renderRoute('/projects/7', { signedInAs })

      const dialog = await openShareDialog(user)
      await user.type(dialog.getByLabelText('Search people by email'), 'lin')
      await user.click(await dialog.findByRole('button', { name: 'Add lin@example.com' }))

      expect(
        await screen.findByText('This user does not belong to your organization.'),
      ).toBeInTheDocument()
    })

    it('offers a retry when the search fails', async () => {
      serveProject()
      serveGrants([ADA_OWNER])
      server.use(http.get(apiUrl('/users/'), () => HttpResponse.json({}, { status: 500 })))
      const { user } = renderRoute('/projects/7', { signedInAs })

      const dialog = await openShareDialog(user)
      await user.type(dialog.getByLabelText('Search people by email'), 'lin')
      const retry = await dialog.findByRole('button', { name: 'Try again' })
      servePeople([LIN])
      await user.click(retry)

      expect(await dialog.findByRole('button', { name: 'Add lin@example.com' })).toBeInTheDocument()
    })
  })

  describe('changing a level', () => {
    it("changes another person's level", async () => {
      serveProject()
      let grace = GRACE_VIEWER
      server.use(
        http.get(apiUrl(SHARE_PATH), () =>
          HttpResponse.json({ count: 2, results: [ADA_OWNER, grace] }),
        ),
      )
      const share = serveShare(() => {
        grace = { ...GRACE_VIEWER, access_level: 'EDITOR' }
        return HttpResponse.json(grace)
      })
      const { user } = renderRoute('/projects/7', { signedInAs })

      const people = await peopleWithAccess(await openShareDialog(user))
      await user.selectOptions(
        people.getByLabelText('Access level for grace@example.com'),
        'EDITOR',
      )

      expect(
        await screen.findByText('grace@example.com now has Editor access.'),
      ).toBeInTheDocument()
      expect(await share.mock.calls[0][0].request.json()).toEqual({
        user: 2,
        access_level: 'EDITOR',
      })
      expect(people.getByLabelText('Access level for grace@example.com')).toHaveValue('EDITOR')
    })

    it('shows the new level while it is being saved', async () => {
      serveProject()
      serveGrants([ADA_OWNER, GRACE_VIEWER])
      const share = heldResponse(() =>
        HttpResponse.json({ ...GRACE_VIEWER, access_level: 'OWNER' }),
      )
      server.use(http.post(apiUrl(SHARE_PATH), share.resolver))
      const { user } = renderRoute('/projects/7', { signedInAs })

      const people = await peopleWithAccess(await openShareDialog(user))
      const level = people.getByLabelText('Access level for grace@example.com')
      await user.selectOptions(level, 'OWNER')

      expect(level).toHaveValue('OWNER')
      expect(level).toBeDisabled()
      expect(people.getByRole('button', { name: 'Remove grace@example.com' })).toBeDisabled()
      share.release()
      expect(await screen.findByText('grace@example.com now has Owner access.')).toBeInTheDocument()
    })

    it("asks before the user gives up their own Owner access, then shows the API's refusal", async () => {
      serveProject()
      serveGrants([ADA_OWNER, GRACE_VIEWER])
      serveShare(() =>
        HttpResponse.json(
          {
            detail: "Cannot downgrade the project's last Owner. Make someone else an Owner first.",
          },
          { status: 400 },
        ),
      )
      const { user } = renderRoute('/projects/7', { signedInAs })

      const people = await peopleWithAccess(await openShareDialog(user))
      await user.selectOptions(people.getByLabelText('Access level for ada@example.com'), 'EDITOR')
      const confirm = await screen.findByRole('alertdialog', { name: 'Give up Owner access?' })
      await user.click(within(confirm).getByRole('button', { name: 'Change my access' }))

      expect(
        await screen.findByText(
          "Cannot downgrade the project's last Owner. Make someone else an Owner first.",
        ),
      ).toBeInTheDocument()
      expect(people.getByLabelText('Access level for ada@example.com')).toHaveValue('OWNER')
    })

    it('closes once the user has given up their own Owner access', async () => {
      serveProject()
      const list = serveGrants([ADA_OWNER, GRACE_VIEWER])
      serveShare(() => HttpResponse.json({ ...ADA_OWNER, access_level: 'EDITOR' }))
      const { user } = renderRoute('/projects/7', { signedInAs })

      const people = await peopleWithAccess(await openShareDialog(user))
      await user.selectOptions(people.getByLabelText('Access level for ada@example.com'), 'EDITOR')
      serveProject(buildProject({ access_level: 'EDITOR' }))
      await user.click(await screen.findByRole('button', { name: 'Change my access' }))

      expect(await screen.findByText('You now have Editor access.')).toBeInTheDocument()
      await waitFor(() =>
        expect(screen.queryByRole('button', { name: 'Share' })).not.toBeInTheDocument(),
      )
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      // The list is no longer the user's to see, so it isn't asked for again.
      expect(list).toHaveBeenCalledTimes(1)
    })

    it('keeps their Owner access when the user cancels', async () => {
      serveProject()
      serveGrants([ADA_OWNER])
      const share = serveShare(() => HttpResponse.json(ADA_OWNER))
      const { user } = renderRoute('/projects/7', { signedInAs })

      const people = await peopleWithAccess(await openShareDialog(user))
      await user.selectOptions(people.getByLabelText('Access level for ada@example.com'), 'VIEWER')
      await user.click(await screen.findByRole('button', { name: 'Cancel' }))

      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
      expect(people.getByLabelText('Access level for ada@example.com')).toHaveValue('OWNER')
      expect(share).not.toHaveBeenCalled()
    })
  })

  describe('removing people', () => {
    it('removes someone after confirming', async () => {
      serveProject()
      serveGrants([ADA_OWNER, GRACE_VIEWER])
      const revoke = serveRevoke(2, () => new HttpResponse(null, { status: 204 }))
      const { user } = renderRoute('/projects/7', { signedInAs })

      const people = await peopleWithAccess(await openShareDialog(user))
      await user.click(people.getByRole('button', { name: 'Remove grace@example.com' }))
      const confirm = await screen.findByRole('alertdialog', { name: 'Remove grace@example.com?' })
      expect(
        within(confirm).getByText("They'll no longer be able to open this project."),
      ).toBeInTheDocument()
      await user.click(within(confirm).getByRole('button', { name: 'Remove' }))

      expect(await screen.findByText('Removed grace@example.com.')).toBeInTheDocument()
      expect(revoke).toHaveBeenCalledTimes(1)
    })

    it('says a public project stays viewable to the person removed', async () => {
      serveProject(buildProject({ visibility: 'PUBLIC' }))
      serveGrants([ADA_OWNER, GRACE_VIEWER])
      const { user } = renderRoute('/projects/7', { signedInAs })

      const people = await peopleWithAccess(await openShareDialog(user))
      await user.click(people.getByRole('button', { name: 'Remove grace@example.com' }))

      expect(
        await screen.findByText("They'll still be able to view this project, because it's public."),
      ).toBeInTheDocument()
    })

    it("shows the API's refusal to remove the last Owner", async () => {
      serveProject()
      serveGrants([ADA_OWNER])
      serveRevoke(1, () =>
        HttpResponse.json(
          { detail: "Cannot revoke the project's last Owner. Make someone else an Owner first." },
          { status: 400 },
        ),
      )
      const { user } = renderRoute('/projects/7', { signedInAs })

      const people = await peopleWithAccess(await openShareDialog(user))
      await user.click(people.getByRole('button', { name: 'Remove ada@example.com' }))
      const confirm = await screen.findByRole('alertdialog', { name: 'Remove your own access?' })
      await user.click(within(confirm).getByRole('button', { name: 'Remove' }))

      expect(
        await screen.findByText(
          "Cannot revoke the project's last Owner. Make someone else an Owner first.",
        ),
      ).toBeInTheDocument()
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    })

    it('leaves a private project once the user has removed themselves', async () => {
      serveProject()
      serveGrants([ADA_OWNER, buildGrant({ id: 24, user: 4, user_email: 'co@example.com' })])
      serveRevoke(1, () => new HttpResponse(null, { status: 204 }))
      const { router, user } = renderRoute('/projects/7', { signedInAs })

      const people = await peopleWithAccess(await openShareDialog(user))
      await user.click(people.getByRole('button', { name: 'Remove ada@example.com' }))
      await user.click(await screen.findByRole('button', { name: 'Remove' }))

      expect(await screen.findByText('Your access was removed.')).toBeInTheDocument()
      await waitFor(() => expect(router.state.location.pathname).toBe('/projects'))
    })

    it('stays on a public project after the user removes themselves', async () => {
      serveProject(buildProject({ visibility: 'PUBLIC' }))
      serveGrants([ADA_OWNER, buildGrant({ id: 24, user: 4, user_email: 'co@example.com' })])
      serveRevoke(1, () => new HttpResponse(null, { status: 204 }))
      const { router, user } = renderRoute('/projects/7', { signedInAs })

      const people = await peopleWithAccess(await openShareDialog(user))
      await user.click(people.getByRole('button', { name: 'Remove ada@example.com' }))
      expect(
        await screen.findByText("You'll still be able to view this project, because it's public."),
      ).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Remove' }))

      expect(await screen.findByText('Your access was removed.')).toBeInTheDocument()
      expect(router.state.location.pathname).toBe('/projects/7')
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('goes back a page after removing the only person on the last one', async () => {
      serveProject()
      server.use(
        http.get(apiUrl(SHARE_PATH), ({ request }) => {
          const page = new URL(request.url).searchParams.get('page')
          return HttpResponse.json({
            count: 21,
            results: page === '2' ? [GRACE_VIEWER] : [ADA_OWNER],
          })
        }),
      )
      serveRevoke(2, () => new HttpResponse(null, { status: 204 }))
      const { user } = renderRoute('/projects/7', { signedInAs })

      const dialog = await openShareDialog(user)
      await user.click(await dialog.findByRole('button', { name: 'Next' }))
      await user.click(await dialog.findByRole('button', { name: 'Remove grace@example.com' }))
      await user.click(await screen.findByRole('button', { name: 'Remove' }))

      expect(await dialog.findByText('Page 1 of 2')).toBeInTheDocument()
    })
  })
})
