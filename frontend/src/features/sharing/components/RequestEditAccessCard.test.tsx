import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { AccessRequest, Document } from '@/api/types'
import { formatDate } from '@/lib/format'
import { buildAccessRequest, buildCurrentUser, buildDocument } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, heldResponse, server, spyResolver } from '@/test/server'

const MY_REQUESTS_PATH = '/documents/access-requests/mine/'
const signedInAs = buildCurrentUser()

function serveDocument(document: Document = buildDocument({ access_level: 'VIEWER' })) {
  server.use(http.get(apiUrl('/documents/11/'), () => HttpResponse.json(document)))
}

function serveMyRequests(requests: AccessRequest[]) {
  const list = spyResolver(() => HttpResponse.json({ count: requests.length, results: requests }))
  server.use(http.get(apiUrl(MY_REQUESTS_PATH), list))
  return list
}

function serveRequestCreate(response: () => Response) {
  const create = spyResolver(response)
  server.use(http.post(apiUrl('/documents/11/access-requests/'), create))
  return create
}

describe('RequestEditAccessCard', () => {
  it('lets a Viewer ask for edit access, then shows the request as waiting', async () => {
    serveDocument()
    let myRequests: AccessRequest[] = []
    const list = spyResolver(() =>
      HttpResponse.json({ count: myRequests.length, results: myRequests }),
    )
    server.use(http.get(apiUrl(MY_REQUESTS_PATH), list))
    const create = serveRequestCreate(() => {
      myRequests = [buildAccessRequest()]
      return HttpResponse.json(myRequests[0], { status: 201 })
    })
    const { user } = renderRoute('/documents/11', { signedInAs })

    await user.click(await screen.findByRole('button', { name: 'Request edit access' }))

    expect(
      await screen.findByText("Request sent. You'll get an email when an owner answers."),
    ).toBeInTheDocument()
    expect(
      await screen.findByText(
        `You asked on ${formatDate('2026-09-20T09:00:00Z')}. Waiting for an owner to answer.`,
      ),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Request edit access' })).not.toBeInTheDocument()
    expect(create).toHaveBeenCalledTimes(1)
    expect(new URL(list.mock.calls[0][0].request.url).searchParams.get('document')).toBe('11')
  })

  it('keeps the button busy while the request is sent', async () => {
    serveDocument()
    const create = heldResponse(() => HttpResponse.json(buildAccessRequest(), { status: 201 }))
    server.use(http.post(apiUrl('/documents/11/access-requests/'), create.resolver))
    const { user } = renderRoute('/documents/11', { signedInAs })

    const button = await screen.findByRole('button', { name: 'Request edit access' })
    await user.click(button)

    expect(button).toBeDisabled()
    create.release()
    expect(await screen.findByText(/^Request sent/)).toBeInTheDocument()
  })

  it('shows a request that is still waiting instead of the button', async () => {
    serveDocument()
    serveMyRequests([buildAccessRequest()])
    renderRoute('/documents/11', { signedInAs })

    expect(await screen.findByText(/Waiting for an owner to answer/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Request edit access' })).not.toBeInTheDocument()
  })

  it('says when the last request was denied, and lets the Viewer ask again', async () => {
    serveDocument()
    serveMyRequests([buildAccessRequest({ status: 'DENIED', modified: '2026-09-22T09:00:00Z' })])
    renderRoute('/documents/11', { signedInAs })

    expect(
      await screen.findByText(
        `Your last request was denied on ${formatDate('2026-09-22T09:00:00Z')}.`,
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Request edit access' })).toBeInTheDocument()
  })

  it("reports the API's reason when the request is refused", async () => {
    serveDocument()
    serveRequestCreate(() =>
      HttpResponse.json(
        { detail: 'You already have a pending request for this document.' },
        { status: 400 },
      ),
    )
    const { user } = renderRoute('/documents/11', { signedInAs })

    await user.click(await screen.findByRole('button', { name: 'Request edit access' }))

    expect(
      await screen.findByText('You already have a pending request for this document.'),
    ).toBeInTheDocument()
  })

  it('is not offered to someone who can already edit', async () => {
    serveDocument(buildDocument({ access_level: 'EDITOR' }))
    renderRoute('/documents/11', { signedInAs })

    expect(await screen.findByLabelText('Content')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Editing' })).not.toBeInTheDocument()
  })
})
