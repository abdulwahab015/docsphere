import { focusManager } from '@tanstack/react-query'
import { act, screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { Notification } from '@/api/types'
import { buildCurrentUser, buildDocument, buildNotification } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const signedInAs = buildCurrentUser()

function serveUnreadCount(count: number) {
  server.use(http.get(apiUrl('/notifications/unread-count/'), () => HttpResponse.json({ count })))
}

function serveNotifications(notifications: Notification[]) {
  server.use(
    http.get(apiUrl('/notifications/'), () =>
      HttpResponse.json({ count: notifications.length, results: notifications }),
    ),
  )
}

async function openBell(user: ReturnType<typeof renderRoute>['user'], name: string | RegExp) {
  await user.click(await screen.findByRole('button', { name }))
  return screen.findByRole('menu')
}

describe('NotificationBell', () => {
  afterEach(() => {
    focusManager.setFocused(undefined)
  })

  it('shows how many notifications are unread', async () => {
    serveUnreadCount(3)
    renderRoute('/projects', { signedInAs })

    const bell = await screen.findByRole('button', { name: 'Notifications, 3 unread' })
    expect(bell).toHaveTextContent('3')
  })

  it('caps the badge, and shows none when everything is read', async () => {
    serveUnreadCount(12)
    renderRoute('/projects', { signedInAs })

    expect(
      await screen.findByRole('button', { name: 'Notifications, 12 unread' }),
    ).toHaveTextContent('9+')

    serveUnreadCount(0)
    act(() => {
      focusManager.setFocused(false)
      focusManager.setFocused(true)
    })

    expect(await screen.findByRole('button', { name: 'Notifications' })).toHaveTextContent('')
  })

  it('asks again when the tab comes back into focus', async () => {
    renderRoute('/projects', { signedInAs })
    await screen.findByRole('button', { name: 'Notifications' })

    serveUnreadCount(1)
    act(() => {
      focusManager.setFocused(false)
      focusManager.setFocused(true)
    })

    expect(
      await screen.findByRole('button', { name: 'Notifications, 1 unread' }),
    ).toBeInTheDocument()
  })

  it('lists the latest, unread ones marked', async () => {
    serveUnreadCount(1)
    serveNotifications([
      buildNotification({ id: 2 }),
      buildNotification({ id: 1, verb: 'ACCESS_REQUEST_DENIED', read: true, details: {} }),
    ])
    const { user } = renderRoute('/projects', { signedInAs })

    const menu = await openBell(user, 'Notifications, 1 unread')

    const [shared, denied] = await within(menu).findAllByRole('menuitem', { name: /Grace Hopper/ })
    expect(shared).toHaveTextContent('Unread: Grace Hopper shared "Q3 plan" with you as Editor')
    expect(denied).toHaveTextContent('Grace Hopper denied your request to edit "Q3 plan"')
    expect(denied).not.toHaveTextContent('Unread')
  })

  it('says when there are none, or they failed to load', async () => {
    const { user } = renderRoute('/projects', { signedInAs })

    expect(
      await within(await openBell(user, 'Notifications')).findByText('Nothing yet.'),
    ).toBeInTheDocument()
    await user.keyboard('{Escape}')

    server.use(http.get(apiUrl('/notifications/'), () => HttpResponse.json({}, { status: 404 })))
    expect(
      await within(await openBell(user, 'Notifications')).findByText(
        "Couldn't load your notifications.",
      ),
    ).toBeInTheDocument()
  })

  it('opening an unread one marks it read and goes to what it is about', async () => {
    serveUnreadCount(1)
    serveNotifications([buildNotification()])
    server.use(http.get(apiUrl('/documents/11/'), () => HttpResponse.json(buildDocument())))
    const markRead = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(http.post(apiUrl('/notifications/51/read/'), markRead))
    const { router, user } = renderRoute('/projects', { signedInAs })
    const menu = await openBell(user, 'Notifications, 1 unread')

    serveUnreadCount(0)
    await user.click(await within(menu).findByRole('menuitem', { name: /shared "Q3 plan"/ }))

    expect(router.state.location.pathname).toBe('/documents/11')
    expect(await screen.findByRole('button', { name: 'Notifications' })).toBeInTheDocument()
    expect(markRead).toHaveBeenCalledTimes(1)
  })

  it("opening a read one about something they can't open marks nothing and stays put", async () => {
    serveNotifications([buildNotification({ read: true, resource_id: null, resource_name: null })])
    const markRead = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(http.post(apiUrl('/notifications/:id/read/'), markRead))
    const { router, user } = renderRoute('/projects', { signedInAs })
    const menu = await openBell(user, 'Notifications')

    await user.click(await within(menu).findByRole('menuitem'))

    expect(router.state.location.pathname).toBe('/projects')
    expect(markRead).not.toHaveBeenCalled()
  })

  it('marks everything read', async () => {
    serveUnreadCount(2)
    serveNotifications([buildNotification()])
    const markAll = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(http.post(apiUrl('/notifications/read-all/'), markAll))
    const { user } = renderRoute('/projects', { signedInAs })
    const menu = await openBell(user, 'Notifications, 2 unread')

    serveUnreadCount(0)
    serveNotifications([buildNotification({ read: true })])
    await user.click(within(menu).getByRole('menuitem', { name: 'Mark all as read' }))

    expect(await screen.findByRole('button', { name: 'Notifications' })).toBeInTheDocument()
    expect(markAll).toHaveBeenCalledTimes(1)
  })
})
