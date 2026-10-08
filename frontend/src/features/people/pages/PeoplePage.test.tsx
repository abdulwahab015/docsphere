import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { RosterUser } from '@/api/types'
import { buildCurrentUser, buildRosterUser } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const PEOPLE_PATH = '/users/'

function buildPeople(count: number, firstId = 1): RosterUser[] {
  return Array.from({ length: count }, (_unused, index) =>
    buildRosterUser({ id: firstId + index, email: `person${firstId + index}@example.com` }),
  )
}

/** Serves `/users/` from `people`, honouring `page` and `search` like DRF. */
function servePeople(people: RosterUser[]) {
  const list = spyResolver(({ request }) => {
    const params = new URL(request.url).searchParams
    const search = params.get('search') ?? ''
    const page = Number(params.get('page') ?? 1)
    const matches = people.filter(
      (person) => person.email.includes(search) || person.name.toLowerCase().includes(search),
    )
    const results = matches.slice((page - 1) * 20, page * 20)
    if (page > 1 && !results.length) {
      return HttpResponse.json({ detail: 'Invalid page.' }, { status: 404 })
    }
    return HttpResponse.json({ count: matches.length, results })
  })
  server.use(http.get(apiUrl(PEOPLE_PATH), list))
  return list
}

function lastRequestParams(list: ReturnType<typeof servePeople>) {
  const [info] = list.mock.calls.at(-1) ?? []
  return info ? new URL(info.request.url).searchParams : undefined
}

describe('PeoplePage', () => {
  it("lists the organization's members and marks the signed-in user", async () => {
    servePeople([buildRosterUser({ id: 1, email: 'ada@example.com' }), ...buildPeople(2, 2)])
    renderRoute('/people', { signedInAs: buildCurrentUser() })

    expect(await screen.findByText('Showing 1–3 of 3')).toBeInTheDocument()
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(3)
    expect(rows[0]).toHaveTextContent('ada@example.comYou')
    expect(document.title).toBe('People · DocSphere')
  })

  it("shows each person's name, with their email address beneath it", async () => {
    servePeople([
      buildRosterUser({ id: 1, email: 'ada@example.com' }),
      buildRosterUser({ id: 2, email: 'grace@example.com', name: 'Grace Hopper' }),
    ])
    renderRoute('/people', { signedInAs: buildCurrentUser() })

    expect(await screen.findByText('Showing 1–2 of 2')).toBeInTheDocument()
    const table = screen.getByRole('table')
    expect(within(table).getByRole('columnheader', { name: 'Person' })).toBeInTheDocument()
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows[0]).toHaveTextContent('ada@example.comYou')
    expect(rows[1]).toHaveTextContent('Grace Hoppergrace@example.com')
  })

  it('finds people by name too', async () => {
    const list = servePeople([
      buildRosterUser({ id: 1, email: 'ada@example.com' }),
      buildRosterUser({ id: 2, email: 'grace@example.com', name: 'Grace Hopper' }),
    ])
    const { user } = renderRoute('/people', { signedInAs: buildCurrentUser() })
    await screen.findByRole('table')

    await user.type(screen.getByRole('searchbox', { name: 'Search people' }), 'hopper')

    expect(await screen.findByText('Showing 1–1 of 1')).toBeInTheDocument()
    expect(lastRequestParams(list)?.get('search')).toBe('hopper')
    expect(screen.getByText('Grace Hopper')).toBeInTheDocument()
  })

  it('searches by email once typing pauses, and keeps the search in the URL', async () => {
    const list = servePeople([
      buildRosterUser({ id: 1, email: 'ada@example.com' }),
      ...buildPeople(3, 2),
    ])
    const { router, user } = renderRoute('/people', { signedInAs: buildCurrentUser() })
    await screen.findByRole('table')

    await user.type(screen.getByRole('searchbox', { name: 'Search people' }), 'person3')

    expect(await screen.findByText('Showing 1–1 of 1')).toBeInTheDocument()
    expect(lastRequestParams(list)?.get('search')).toBe('person3')
    expect(router.state.location.search).toBe('?search=person3')
    // One request for the page, one for the finished search, none per keystroke.
    expect(list).toHaveBeenCalledTimes(2)
  })

  it('clears the search from the URL when the box is emptied', async () => {
    servePeople(buildPeople(3))
    const { router, user } = renderRoute('/people?search=person1', {
      signedInAs: buildCurrentUser(),
    })
    await screen.findByText('Showing 1–1 of 1')

    await user.clear(screen.getByRole('searchbox', { name: 'Search people' }))

    expect(await screen.findByText('Showing 1–3 of 3')).toBeInTheDocument()
    expect(router.state.location.search).toBe('')
  })

  it('restores the previous search when navigating back', async () => {
    servePeople(buildPeople(3))
    const { router } = renderRoute('/people?search=person1', {
      signedInAs: buildCurrentUser(),
    })
    await screen.findByText('Showing 1–1 of 1')

    await router.navigate('/people?search=person2')
    await screen.findByDisplayValue('person2')
    await router.navigate(-1)

    expect(await screen.findByDisplayValue('person1')).toBeInTheDocument()
  })

  it('pages through long lists', async () => {
    const list = servePeople(buildPeople(45))
    const { router, user } = renderRoute('/people', { signedInAs: buildCurrentUser() })
    await screen.findByText('Showing 1–20 of 45')

    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByText('Showing 21–40 of 45')).toBeInTheDocument()
    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()
    expect(lastRequestParams(list)?.get('page')).toBe('2')
    expect(router.state.location.search).toBe('?page=2')

    await user.click(screen.getByRole('button', { name: 'Previous' }))

    expect(await screen.findByText('Showing 1–20 of 45')).toBeInTheDocument()
    expect(router.state.location.search).toBe('')
  })

  it('explains when a search matches nobody', async () => {
    servePeople(buildPeople(3))
    renderRoute('/people?search=nobody', { signedInAs: buildCurrentUser() })

    expect(await screen.findByRole('heading', { name: 'No matches' })).toBeInTheDocument()
    expect(screen.getByText(`No one matches "nobody".`)).toBeInTheDocument()
  })

  it('says so when the organization has no members to list', async () => {
    servePeople([])
    renderRoute('/people', { signedInAs: buildCurrentUser() })

    expect(await screen.findByRole('heading', { name: 'No one here yet' })).toBeInTheDocument()
  })

  it('shows "not found" for a page past the end', async () => {
    servePeople(buildPeople(3))
    renderRoute('/people?page=9', { signedInAs: buildCurrentUser() })

    expect(await screen.findByRole('heading', { name: 'Not found' })).toBeInTheDocument()
  })

  it('offers a retry when loading fails', async () => {
    server.use(http.get(apiUrl(PEOPLE_PATH), () => HttpResponse.json({}, { status: 500 })))
    const { user } = renderRoute('/people', { signedInAs: buildCurrentUser() })

    expect(await screen.findByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument()

    servePeople(buildPeople(2))
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('Showing 1–2 of 2')).toBeInTheDocument()
  })
})
