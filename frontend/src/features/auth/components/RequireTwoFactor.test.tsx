import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { findAccountMenu } from '@/test/actions'
import {
  buildCurrentUser,
  buildOrganizationSummary,
  buildRecoveryCodes,
  buildTwoFactorSetup,
} from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const held = buildCurrentUser({
  organization: buildOrganizationSummary({ name: 'Acme', require_two_factor: true }),
})

function serveSetup() {
  const confirm = spyResolver(() => HttpResponse.json(buildRecoveryCodes()))
  server.use(
    http.post(apiUrl('/users/me/two-factor/setup/'), () =>
      HttpResponse.json(buildTwoFactorSetup()),
    ),
    http.post(apiUrl('/users/me/two-factor/confirm/'), confirm),
  )
  return confirm
}

describe('RequireTwoFactor', () => {
  it('lets someone in when their organization requires it and they have it on', async () => {
    renderRoute('/projects', { signedInAs: { ...held, two_factor_enabled: true } })

    expect(await findAccountMenu()).toBeInTheDocument()
  })

  it('lets everyone in when their organization does not require it', async () => {
    renderRoute('/projects', { signedInAs: buildCurrentUser() })

    expect(await findAccountMenu()).toBeInTheDocument()
  })

  it('holds someone without it at the setup screen, which they can leave by logging out', async () => {
    renderRoute('/projects', { signedInAs: held })

    expect(
      await screen.findByRole('heading', { name: 'Set up two-factor sign-in' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Acme requires a code from an authenticator app each time you log in.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Account menu' })).not.toBeInTheDocument()
  })

  it('lets them in once it is set up and the recovery codes are saved', async () => {
    const confirm = serveSetup()
    // The session re-read after setup says it's on.
    server.use(
      http.get(apiUrl('/users/me/'), () =>
        HttpResponse.json({ ...held, two_factor_enabled: true }),
      ),
    )
    const { user } = renderRoute('/projects', { signedInAs: held })

    await user.click(await screen.findByRole('button', { name: 'Get started' }))
    expect(await screen.findByTitle('QR code for your authenticator app')).toBeInTheDocument()
    expect(screen.getByText('JBSW Y3DP EHPK 3PXP JBSW Y3DP EHPK 3PXP')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Code from your app'), '123456')
    await user.click(screen.getByRole('button', { name: 'Turn on' }))

    // The codes stay up until they're saved, even though it's on now.
    const codes = await screen.findByRole('list', { name: 'Recovery codes' })
    expect(codes.children).toHaveLength(10)
    expect(await confirm.mock.calls[0][0].request.json()).toEqual({ otp: '123456' })
    await user.click(screen.getByRole('button', { name: "I've saved them" }))

    expect(await findAccountMenu()).toBeInTheDocument()
  })

  it('checks the code looks right before sending it', async () => {
    const confirm = serveSetup()
    const { user } = renderRoute('/projects', { signedInAs: held })

    await user.click(await screen.findByRole('button', { name: 'Get started' }))
    await user.type(await screen.findByLabelText('Code from your app'), '12ab')
    await user.click(screen.getByRole('button', { name: 'Turn on' }))

    expect(await screen.findByText('Enter the 6-digit code from your app.')).toBeInTheDocument()
    expect(confirm).not.toHaveBeenCalled()
  })

  it("puts the API's reason under the code when it's wrong", async () => {
    serveSetup()
    server.use(
      http.post(apiUrl('/users/me/two-factor/confirm/'), () =>
        HttpResponse.json(
          { otp: ["That code didn't work. Enter the code your app shows now."] },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderRoute('/projects', { signedInAs: held })

    await user.click(await screen.findByRole('button', { name: 'Get started' }))
    await user.type(await screen.findByLabelText('Code from your app'), '000000')
    await user.click(screen.getByRole('button', { name: 'Turn on' }))

    expect(await screen.findByText(/That code didn't work/)).toBeInTheDocument()
  })

  it('says so when setup could not start', async () => {
    server.use(
      http.post(apiUrl('/users/me/two-factor/setup/'), () =>
        HttpResponse.json({}, { status: 500 }),
      ),
    )
    const { user } = renderRoute('/projects', { signedInAs: held })

    await user.click(await screen.findByRole('button', { name: 'Get started' }))

    expect(
      await screen.findByText("Couldn't start setting up two-factor sign-in."),
    ).toBeInTheDocument()
  })
})
