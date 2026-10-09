import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const VERIFY_PATH = '/users/auth/verify-email/'

describe('VerifyEmailPage', () => {
  it('verifies the address as soon as the link is opened, once', async () => {
    const verify = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(http.post(apiUrl(VERIFY_PATH), verify))
    renderRoute('/verify-email?token=signed-token')

    expect(await screen.findByRole('heading', { name: 'Email verified' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Continue to DocSphere' })).toHaveAttribute('href', '/')
    expect(verify).toHaveBeenCalledOnce()
    expect(await verify.mock.calls[0][0].request.json()).toEqual({ token: 'signed-token' })
  })

  it('explains when the link is no good, and where to get a new one', async () => {
    server.use(
      http.post(apiUrl(VERIFY_PATH), () =>
        HttpResponse.json({ token: ['This link is invalid or has expired.'] }, { status: 400 }),
      ),
    )
    renderRoute('/verify-email?token=old-token')

    expect(
      await screen.findByRole('heading', { name: "Couldn't verify your email" }),
    ).toBeInTheDocument()
    expect(screen.getByText('This link is invalid or has expired.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Log in to get a new link' })).toBeInTheDocument()
  })

  it('rejects a link missing its token', () => {
    renderRoute('/verify-email')

    expect(screen.getByRole('heading', { name: 'Invalid verification link' })).toBeInTheDocument()
  })
})
