import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { AccessRequest } from '@/api/types'
import { buildAccessRequest, buildCurrentUser } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, heldResponse, server, spyResolver } from '@/test/server'

const INCOMING_PATH = '/documents/access-requests/incoming/'
const MINE_PATH = '/documents/access-requests/mine/'
const signedInAs = buildCurrentUser()
const FROM_GRACE = buildAccessRequest()
const FROM_LIN = buildAccessRequest({
  id: 32,
  document: 12,
  document_title: 'Budget',
  requested_by: 3,
  requested_by_email: 'lin@example.com',
})

function serveList(path: string, requests: AccessRequest[], { count = requests.length } = {}) {
  const list = spyResolver(() => HttpResponse.json({ count, results: requests }))
  server.use(http.get(apiUrl(path), list))
  return list
}

function serveReview(
  accessRequest: AccessRequest,
  decision: 'approve' | 'deny',
  response: () => Response,
) {
  const review = spyResolver(response)
  server.use(
    http.post(
      apiUrl(
        `/documents/${accessRequest.document}/access-requests/${accessRequest.id}/${decision}/`,
      ),
      review,
    ),
  )
  return review
}

function rowFor(text: string) {
  return within(screen.getByRole('row', { name: new RegExp(text) }))
}

describe('RequestsPage', () => {
  describe('incoming requests', () => {
    it('lists requests waiting for an answer, with links to their documents', async () => {
      serveList(INCOMING_PATH, [FROM_GRACE, FROM_LIN])
      renderRoute('/requests', { signedInAs })

      expect(
        await screen.findByRole('heading', { level: 1, name: 'Access requests' }),
      ).toBeInTheDocument()
      expect(await screen.findByRole('link', { name: 'Findings' })).toHaveAttribute(
        'href',
        '/documents/11',
      )
      expect(rowFor('Budget').getByText('lin@example.com')).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: 'Incoming' })).toHaveAttribute('aria-selected', 'true')
    })

    it('approves a request', async () => {
      const list = serveList(INCOMING_PATH, [FROM_GRACE, FROM_LIN])
      const approve = serveReview(FROM_GRACE, 'approve', () =>
        HttpResponse.json({ ...FROM_GRACE, status: 'APPROVED' }),
      )
      const { user } = renderRoute('/requests', { signedInAs })

      await screen.findByRole('link', { name: 'Findings' })
      serveList(INCOMING_PATH, [FROM_LIN])
      await user.click(rowFor('Findings').getByRole('button', { name: 'Approve' }))

      expect(
        await screen.findByText('grace@example.com can now edit "Findings".'),
      ).toBeInTheDocument()
      expect(approve).toHaveBeenCalledTimes(1)
      await waitFor(() =>
        expect(screen.queryByRole('link', { name: 'Findings' })).not.toBeInTheDocument(),
      )
      expect(list).toHaveBeenCalledTimes(1)
    })

    it('names the person asking, and names them when answering', async () => {
      const fromGrace = buildAccessRequest({ requested_by_name: 'Grace Hopper' })
      serveList(INCOMING_PATH, [fromGrace])
      serveReview(fromGrace, 'approve', () =>
        HttpResponse.json({ ...fromGrace, status: 'APPROVED' }),
      )
      const { user } = renderRoute('/requests', { signedInAs })

      await screen.findByRole('link', { name: 'Findings' })
      expect(rowFor('Findings').getByText('Grace Hopper')).toBeInTheDocument()
      expect(rowFor('Findings').getByText('grace@example.com')).toBeInTheDocument()
      await user.click(rowFor('Findings').getByRole('button', { name: 'Approve' }))

      expect(await screen.findByText('Grace Hopper can now edit "Findings".')).toBeInTheDocument()
    })

    it('denies a request', async () => {
      serveList(INCOMING_PATH, [FROM_GRACE])
      const deny = serveReview(FROM_GRACE, 'deny', () =>
        HttpResponse.json({ ...FROM_GRACE, status: 'DENIED' }),
      )
      const { user } = renderRoute('/requests', { signedInAs })

      await user.click(await screen.findByRole('button', { name: 'Deny' }))

      expect(
        await screen.findByText(`Denied grace@example.com's request for "Findings".`),
      ).toBeInTheDocument()
      expect(deny).toHaveBeenCalledTimes(1)
    })

    it('holds off further answers while one is being sent', async () => {
      serveList(INCOMING_PATH, [FROM_GRACE, FROM_LIN])
      const deny = heldResponse(() => HttpResponse.json({ ...FROM_LIN, status: 'DENIED' }))
      server.use(http.post(apiUrl('/documents/12/access-requests/32/deny/'), deny.resolver))
      const { user } = renderRoute('/requests', { signedInAs })

      await screen.findByRole('link', { name: 'Budget' })
      await user.click(rowFor('Budget').getByRole('button', { name: 'Deny' }))

      for (const button of screen.getAllByRole('button', { name: /^(Approve|Deny)$/ })) {
        expect(button).toBeDisabled()
      }
      deny.release()
      expect(
        await screen.findByText(`Denied lin@example.com's request for "Budget".`),
      ).toBeInTheDocument()
    })

    it('reports a request that could not be answered', async () => {
      serveList(INCOMING_PATH, [FROM_GRACE])
      serveReview(FROM_GRACE, 'approve', () => HttpResponse.json({}, { status: 404 }))
      const { user } = renderRoute('/requests', { signedInAs })

      await user.click(await screen.findByRole('button', { name: 'Approve' }))

      expect(
        await screen.findByText("Couldn't answer grace@example.com's request."),
      ).toBeInTheDocument()
    })

    it('says when there is nothing to answer', async () => {
      serveList(INCOMING_PATH, [])
      renderRoute('/requests', { signedInAs })

      expect(await screen.findByText('Nothing to answer')).toBeInTheDocument()
    })

    it('pages through a long list', async () => {
      const list = serveList(INCOMING_PATH, [FROM_GRACE], { count: 25 })
      const { router, user } = renderRoute('/requests', { signedInAs })

      await user.click(await screen.findByRole('button', { name: 'Next' }))

      await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
      expect(router.state.location.search).toBe('?page=2')
    })

    it('offers a retry when loading fails', async () => {
      server.use(http.get(apiUrl(INCOMING_PATH), () => HttpResponse.json({}, { status: 500 })))
      const { user } = renderRoute('/requests', { signedInAs })

      const retry = await screen.findByRole('button', { name: 'Try again' })
      serveList(INCOMING_PATH, [FROM_GRACE])
      await user.click(retry)

      expect(await screen.findByRole('link', { name: 'Findings' })).toBeInTheDocument()
    })
  })

  describe('sent requests', () => {
    it('lists the user’s own requests and how each was answered', async () => {
      serveList(INCOMING_PATH, [])
      serveList(MINE_PATH, [
        buildAccessRequest({ requested_by: 1, requested_by_email: 'ada@example.com' }),
        buildAccessRequest({
          id: 33,
          document: 12,
          document_title: 'Budget',
          status: 'APPROVED',
          reviewed_by: 4,
          reviewed_by_email: 'owner@example.com',
        }),
      ])
      const { router, user } = renderRoute('/requests', { signedInAs })

      await user.click(await screen.findByRole('tab', { name: 'Sent' }))

      expect(await screen.findByRole('link', { name: 'Budget' })).toBeInTheDocument()
      expect(rowFor('Budget').getByText('Approved')).toBeInTheDocument()
      expect(rowFor('Budget').getByText('owner@example.com')).toBeInTheDocument()
      expect(rowFor('Findings').getByText('Pending')).toBeInTheDocument()
      expect(rowFor('Findings').getByText('—')).toBeInTheDocument()
      expect(router.state.location.search).toBe('?tab=sent')
    })

    it('names whoever answered', async () => {
      serveList(INCOMING_PATH, [])
      serveList(MINE_PATH, [
        buildAccessRequest({
          status: 'APPROVED',
          reviewed_by: 4,
          reviewed_by_email: 'owner@example.com',
          reviewed_by_name: 'Olive Owner',
        }),
      ])
      const { user } = renderRoute('/requests', { signedInAs })

      await user.click(await screen.findByRole('tab', { name: 'Sent' }))

      expect(await screen.findByRole('link', { name: 'Findings' })).toBeInTheDocument()
      expect(rowFor('Findings').getByText('Olive Owner')).toBeInTheDocument()
    })

    it('opens on the sent tab from its link, and goes back to incoming', async () => {
      serveList(MINE_PATH, [])
      serveList(INCOMING_PATH, [])
      const { router, user } = renderRoute('/requests?tab=sent', { signedInAs })

      expect(await screen.findByText('No requests sent')).toBeInTheDocument()
      await user.click(screen.getByRole('tab', { name: 'Incoming' }))

      expect(await screen.findByText('Nothing to answer')).toBeInTheDocument()
      expect(router.state.location.search).toBe('')
    })

    it('offers a retry when loading fails', async () => {
      server.use(http.get(apiUrl(MINE_PATH), () => HttpResponse.json({}, { status: 500 })))
      const { user } = renderRoute('/requests?tab=sent', { signedInAs })

      const retry = await screen.findByRole('button', { name: 'Try again' })
      serveList(MINE_PATH, [FROM_GRACE])
      await user.click(retry)

      expect(await screen.findByRole('link', { name: 'Findings' })).toBeInTheDocument()
    })
  })
})
