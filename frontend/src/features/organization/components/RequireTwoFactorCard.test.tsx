import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { buildCurrentUser, buildOrganization } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const PROFILE_PATH = '/organizations/profile/'
const adminWithTwoFactor = buildCurrentUser({ org_role: 'ADMIN', two_factor_enabled: true })

function serveProfile(requireTwoFactor: boolean) {
  server.use(
    http.get(apiUrl(PROFILE_PATH), () =>
      HttpResponse.json(buildOrganization({ require_two_factor: requireTwoFactor })),
    ),
  )
}

describe('RequireTwoFactorCard', () => {
  it('requires two-factor sign-in after confirming', async () => {
    serveProfile(false)
    const update = spyResolver(() =>
      HttpResponse.json(buildOrganization({ require_two_factor: true })),
    )
    server.use(http.patch(apiUrl(PROFILE_PATH), update))
    const { user } = renderRoute('/settings/organization', { signedInAs: adminWithTwoFactor })

    await user.click(await screen.findByRole('button', { name: 'Require two-factor sign-in' }))
    const confirm = await screen.findByRole('alertdialog')
    expect(confirm).toHaveAccessibleName('Require two-factor sign-in?')
    await user.click(within(confirm).getByRole('button', { name: 'Require it' }))

    expect(await screen.findByText('Two-factor sign-in is now required.')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'Stop requiring it' })).toBeInTheDocument()
    expect(await update.mock.calls[0][0].request.json()).toEqual({ require_two_factor: true })
  })

  it('stops requiring it', async () => {
    serveProfile(true)
    const update = spyResolver(() =>
      HttpResponse.json(buildOrganization({ require_two_factor: false })),
    )
    server.use(http.patch(apiUrl(PROFILE_PATH), update))
    const { user } = renderRoute('/settings/organization', { signedInAs: adminWithTwoFactor })

    await user.click(await screen.findByRole('button', { name: 'Stop requiring it' }))

    expect(await screen.findByText('Two-factor sign-in is no longer required.')).toBeInTheDocument()
    expect(await update.mock.calls[0][0].request.json()).toEqual({ require_two_factor: false })
  })

  it('asks an admin without it to turn it on for themselves first', async () => {
    serveProfile(false)
    renderRoute('/settings/organization', {
      signedInAs: buildCurrentUser({ org_role: 'ADMIN' }),
    })

    expect(await screen.findByRole('button', { name: 'Require two-factor sign-in' })).toBeDisabled()
    expect(screen.getByRole('link', { name: 'account settings' })).toHaveAttribute(
      'href',
      '/settings/account',
    )
  })

  it("shows the API's reason when it refuses", async () => {
    serveProfile(false)
    server.use(
      http.patch(apiUrl(PROFILE_PATH), () =>
        HttpResponse.json(
          {
            require_two_factor: [
              'Turn on two-factor sign-in for your own account before requiring it.',
            ],
          },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderRoute('/settings/organization', { signedInAs: adminWithTwoFactor })

    await user.click(await screen.findByRole('button', { name: 'Require two-factor sign-in' }))
    await user.click(
      within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Require it' }),
    )

    expect(
      await screen.findByText(
        'Turn on two-factor sign-in for your own account before requiring it.',
      ),
    ).toBeInTheDocument()
  })
})
