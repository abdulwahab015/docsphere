import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { Notification } from '@/api/types'
import { buildCurrentUser, buildDocument, buildNotification } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const signedInAs = buildCurrentUser()

function serveNotifications(notifications: Notification[], count = notifications.length) {
  const spy = spyResolver(() => HttpResponse.json({ count, results: notifications }))
  server.use(http.get(apiUrl('/notifications/'), spy))
  return spy
}

describe('NotificationsPage', () => {
  it('lists every notification, unread ones marked, a page at a time', async () => {
    const list = serveNotifications(
      [
        buildNotification({ id: 2 }),
        buildNotification({ id: 1, verb: 'ACCESS_REQUEST_DENIED', read: true, details: {} }),
      ],
      25,
    )
    const { user } = renderRoute('/notifications', { signedInAs })

    const items = within(await screen.findByRole('list', { name: 'Notifications' })).getAllByRole(
      'listitem',
    )
    expect(items[0]).toHaveTextContent('Unread: Grace Hopper shared "Q3 plan" with you as Editor')
    expect(items[1]).not.toHaveTextContent('Unread')
    expect(screen.getByText('Showing 1–20 of 25')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /next/i }))

    await vi.waitFor(() =>
      expect(new URL(list.mock.calls.at(-1)![0].request.url).searchParams.get('page')).toBe('2'),
    )
  })

  it('opening one marks it read and goes to what it is about', async () => {
    serveNotifications([buildNotification()])
    server.use(http.get(apiUrl('/documents/11/'), () => HttpResponse.json(buildDocument())))
    const markRead = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(http.post(apiUrl('/notifications/51/read/'), markRead))
    const { router, user } = renderRoute('/notifications', { signedInAs })

    await user.click(await screen.findByRole('button', { name: /shared "Q3 plan"/ }))

    expect(router.state.location.pathname).toBe('/documents/11')
    expect(markRead).toHaveBeenCalledTimes(1)
  })

  it('marks them all read', async () => {
    serveNotifications([buildNotification()])
    server.use(
      http.get(apiUrl('/notifications/unread-count/'), () => HttpResponse.json({ count: 1 })),
    )
    const markAll = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(http.post(apiUrl('/notifications/read-all/'), markAll))
    const { user } = renderRoute('/notifications', { signedInAs })

    await user.click(await screen.findByRole('button', { name: 'Mark all as read' }))

    expect(markAll).toHaveBeenCalledTimes(1)
  })

  it('says when there are none, and offers to try again after a failure', async () => {
    renderRoute('/notifications', { signedInAs })
    expect(await screen.findByRole('heading', { name: 'No notifications yet' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mark all as read' })).not.toBeInTheDocument()
  })

  it('offers to try again when they fail to load', async () => {
    server.use(http.get(apiUrl('/notifications/'), () => HttpResponse.json({}, { status: 500 })))
    const { user } = renderRoute('/notifications', { signedInAs })
    const tryAgain = await screen.findByRole('button', { name: 'Try again' })

    serveNotifications([buildNotification()])
    await user.click(tryAgain)

    expect(await screen.findByRole('list', { name: 'Notifications' })).toBeInTheDocument()
  })
})
