import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { REFRESH_PATH } from '@/api/constants'
import { buildCurrentUser, buildTokenPair } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server } from '@/test/server'

describe('SessionLoader', () => {
  it('restores a session from the refresh cookie on page load', async () => {
    server.use(
      http.post(apiUrl(REFRESH_PATH), () => HttpResponse.json(buildTokenPair())),
      http.get(apiUrl('/users/me/'), () => HttpResponse.json(buildCurrentUser())),
    )
    renderRoute('/')

    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    expect(await screen.findByText(/Signed in as ada@example.com/)).toBeInTheDocument()
  })

  it('offers a retry when the server is unreachable', async () => {
    server.use(http.post(apiUrl(REFRESH_PATH), () => HttpResponse.error()))
    const { user } = renderRoute('/')

    expect(await screen.findByRole('heading', { name: "Can't load DocSphere" })).toBeInTheDocument()

    server.resetHandlers()
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
  })
})
