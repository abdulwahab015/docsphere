import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import {
  buildCurrentUser,
  buildOrganizationSummary,
  buildRecoveryCodes,
  buildTwoFactorSetup,
  buildTwoFactorStatus,
} from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const STATUS_PATH = '/users/me/two-factor/'
const withTwoFactor = buildCurrentUser({ two_factor_enabled: true })

function serveStatus(...statuses: ReturnType<typeof buildTwoFactorStatus>[]) {
  let answered = 0
  const status = spyResolver(() =>
    HttpResponse.json(statuses[Math.min(answered++, statuses.length - 1)]),
  )
  server.use(http.get(apiUrl(STATUS_PATH), status))
  return status
}

function card() {
  return within(
    screen.getByRole('heading', { name: /Two-factor sign-in/ }).closest('[data-slot="card"]')!,
  )
}

describe('TwoFactorCard', () => {
  it('turns it on from the account page', async () => {
    const status = serveStatus(
      buildTwoFactorStatus(),
      buildTwoFactorStatus({ enabled: true, recovery_codes_left: 10 }),
    )
    const me = spyResolver(() => HttpResponse.json(withTwoFactor))
    server.use(
      http.post(apiUrl(`${STATUS_PATH}setup/`), () => HttpResponse.json(buildTwoFactorSetup())),
      http.post(apiUrl(`${STATUS_PATH}confirm/`), () => HttpResponse.json(buildRecoveryCodes())),
      http.get(apiUrl('/users/me/'), me),
    )
    const { user } = renderRoute('/settings/account', { signedInAs: buildCurrentUser() })

    await user.click(await screen.findByRole('button', { name: 'Turn on two-factor sign-in' }))
    const dialog = within(await screen.findByRole('dialog'))
    await user.click(dialog.getByRole('button', { name: 'Get started' }))
    await user.type(await dialog.findByLabelText('Code from your app'), '123456')
    await user.click(dialog.getByRole('button', { name: 'Turn on' }))
    expect(await screen.findByText('Two-factor sign-in is on.')).toBeInTheDocument()
    // Nothing is re-read while the codes are up: the card would switch to "on"
    // and take the dialog, and the codes shown only once, with it.
    expect(await dialog.findByRole('list', { name: 'Recovery codes' })).toBeInTheDocument()
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(status).toHaveBeenCalledOnce()
    await user.click(dialog.getByRole('button', { name: "I've saved them" }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await card().findByText('You have 10 recovery codes left.')).toBeInTheDocument()
    expect(card().getByText('On')).toBeInTheDocument()
    // The session is re-read, so the app knows it's on.
    await waitFor(() => expect(me).toHaveBeenCalled())
  })

  it('says how many recovery codes are left, and suggests new ones when few are', async () => {
    serveStatus(buildTwoFactorStatus({ enabled: true, recovery_codes_left: 2 }))
    renderRoute('/settings/account', { signedInAs: withTwoFactor })

    expect(
      await screen.findByText('You have 2 recovery codes left. Make new ones before you run out.'),
    ).toBeInTheDocument()
  })

  it('says when no recovery codes are left', async () => {
    serveStatus(buildTwoFactorStatus({ enabled: true, recovery_codes_left: 0 }))
    renderRoute('/settings/account', { signedInAs: withTwoFactor })

    expect(await screen.findByText(/You have no recovery codes left\./)).toBeInTheDocument()
  })

  it('makes new recovery codes with the password, shown once', async () => {
    serveStatus(buildTwoFactorStatus({ enabled: true, recovery_codes_left: 1 }))
    const make = spyResolver(() => HttpResponse.json(buildRecoveryCodes()))
    server.use(http.post(apiUrl(`${STATUS_PATH}recovery-codes/`), make))
    const { user } = renderRoute('/settings/account', { signedInAs: withTwoFactor })

    await user.click(await screen.findByRole('button', { name: 'New recovery codes' }))
    const form = within(await screen.findByRole('form', { name: 'Make new recovery codes' }))
    await user.type(form.getByLabelText('Current password'), 'Old-Pass-123!')
    await user.click(form.getByRole('button', { name: 'Make new codes' }))

    expect(await screen.findByRole('list', { name: 'Recovery codes' })).toBeInTheDocument()
    expect(await make.mock.calls[0][0].request.json()).toEqual({
      current_password: 'Old-Pass-123!',
    })
    await user.click(screen.getByRole('button', { name: "I've saved them" }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())

    // Opening it again asks for the password again.
    await user.click(screen.getByRole('button', { name: 'New recovery codes' }))
    expect(await screen.findByRole('form', { name: 'Make new recovery codes' })).toBeInTheDocument()
  })

  it('puts a wrong password under the field', async () => {
    serveStatus(buildTwoFactorStatus({ enabled: true, recovery_codes_left: 10 }))
    server.use(
      http.post(apiUrl(`${STATUS_PATH}recovery-codes/`), () =>
        HttpResponse.json(
          { current_password: ['Current password is incorrect.'] },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderRoute('/settings/account', { signedInAs: withTwoFactor })

    await user.click(await screen.findByRole('button', { name: 'New recovery codes' }))
    const form = within(await screen.findByRole('form', { name: 'Make new recovery codes' }))
    await user.type(form.getByLabelText('Current password'), 'wrong')
    await user.click(form.getByRole('button', { name: 'Make new codes' }))

    expect(await form.findByText('Current password is incorrect.')).toBeInTheDocument()
  })

  it('turns it off with the password', async () => {
    serveStatus(
      buildTwoFactorStatus({ enabled: true, recovery_codes_left: 10 }),
      buildTwoFactorStatus(),
    )
    const turnOff = spyResolver(() => new HttpResponse(null, { status: 204 }))
    server.use(
      http.post(apiUrl(`${STATUS_PATH}disable/`), turnOff),
      http.get(apiUrl('/users/me/'), () => HttpResponse.json(buildCurrentUser())),
    )
    const { user } = renderRoute('/settings/account', { signedInAs: withTwoFactor })

    await user.click(await screen.findByRole('button', { name: 'Turn off' }))
    const form = within(await screen.findByRole('form', { name: 'Turn off two-factor sign-in' }))
    await user.click(form.getByRole('button', { name: 'Turn off' }))
    expect(await form.findByText('Enter your current password.')).toBeInTheDocument()
    await user.type(form.getByLabelText('Current password'), 'Old-Pass-123!')
    await user.click(form.getByRole('button', { name: 'Turn off' }))

    expect(await screen.findByText('Two-factor sign-in is off.')).toBeInTheDocument()
    expect(
      await screen.findByRole('button', { name: 'Turn on two-factor sign-in' }),
    ).toBeInTheDocument()
    expect(await turnOff.mock.calls[0][0].request.json()).toEqual({
      current_password: 'Old-Pass-123!',
    })
  })

  it("can't be turned off while the organization requires it", async () => {
    serveStatus(buildTwoFactorStatus({ enabled: true, recovery_codes_left: 10 }))
    renderRoute('/settings/account', {
      signedInAs: buildCurrentUser({
        two_factor_enabled: true,
        organization: buildOrganizationSummary({ name: 'Acme', require_two_factor: true }),
      }),
    })

    expect(await screen.findByRole('button', { name: 'Turn off' })).toBeDisabled()
    expect(
      screen.getByText("Acme requires two-factor sign-in, so it can't be turned off."),
    ).toBeInTheDocument()
  })

  it("says so when it couldn't be read", async () => {
    server.use(http.get(apiUrl(STATUS_PATH), () => HttpResponse.json({}, { status: 500 })))
    renderRoute('/settings/account', { signedInAs: buildCurrentUser() })

    expect(await screen.findByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
