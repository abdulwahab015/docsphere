import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const RESET_REQUEST_PATH = '/users/auth/password-reset/'

describe('ForgotPasswordPage', () => {
  it('confirms without revealing whether the account exists', async () => {
    const requestReset = spyResolver(() => new HttpResponse(null, { status: 200 }))
    server.use(http.post(apiUrl(RESET_REQUEST_PATH), requestReset))
    const { user } = renderRoute('/forgot-password')

    await user.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await user.click(screen.getByRole('button', { name: 'Send reset link' }))

    expect(await screen.findByText(/If an account exists for ada@example.com/)).toBeInTheDocument()
    expect(await requestReset.mock.calls[0][0].request.json()).toEqual({ email: 'ada@example.com' })
  })

  it('shows the rate-limit message when throttled', async () => {
    server.use(
      http.post(apiUrl(RESET_REQUEST_PATH), () =>
        HttpResponse.json(
          { detail: 'Request was throttled. Expected available in 60 seconds.' },
          { status: 429 },
        ),
      ),
    )
    const { user } = renderRoute('/forgot-password')

    await user.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await user.click(screen.getByRole('button', { name: 'Send reset link' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Expected available in 60 seconds.')
  })
})
