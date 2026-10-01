import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { getAccessToken } from '@/api/access-token'
import { REFRESH_PATH } from '@/api/constants'
import { buildCurrentUser, buildTokenPair } from '@/test/factories'
import { findAccountMenu, logOutViaAccountMenu } from '@/test/actions'
import { renderRoute } from '@/test/render'
import { apiUrl, server } from '@/test/server'

const CHANNEL_NAME = 'docsphere-session'
const SESSION_CHANGED = 'session-changed'

// Stands in for the app running in another browser tab.
let otherTab: BroadcastChannel

function nextMessageInOtherTab() {
  return new Promise<unknown>((resolve) => {
    otherTab.addEventListener('message', (event) => resolve(event.data), { once: true })
  })
}

beforeEach(() => {
  otherTab = new BroadcastChannel(CHANNEL_NAME)
})

afterEach(() => {
  otherTab.close()
})

describe('RootLayout', () => {
  describe('when another tab changes the session', () => {
    it('signs this tab out after a logout elsewhere', async () => {
      renderRoute('/', { signedInAs: buildCurrentUser() })

      otherTab.postMessage(SESSION_CHANGED)

      // The shared refresh cookie is gone, so re-reading the session finds nobody.
      expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
      expect(getAccessToken()).toBeNull()
    })

    it('switches to the user another tab signed in as', async () => {
      server.use(
        http.post(apiUrl(REFRESH_PATH), () => HttpResponse.json(buildTokenPair())),
        http.get(apiUrl('/users/me/'), () =>
          HttpResponse.json(buildCurrentUser({ id: 2, email: 'grace@example.com' })),
        ),
      )
      renderRoute('/', { signedInAs: buildCurrentUser() })

      otherTab.postMessage(SESSION_CHANGED)

      await expect
        .poll(async () => (await findAccountMenu()).textContent)
        .toContain('grace@example.com')
    })

    it('ignores unrelated messages on the channel', async () => {
      renderRoute('/', { signedInAs: buildCurrentUser() })

      otherTab.postMessage('something-else')
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(await findAccountMenu()).toHaveTextContent('ada@example.com')
    })
  })

  describe('when this tab changes the session', () => {
    it('announces a sign-in', async () => {
      server.use(
        http.post(apiUrl('/users/auth/login/'), () => HttpResponse.json(buildTokenPair())),
        http.get(apiUrl('/users/me/'), () => HttpResponse.json(buildCurrentUser())),
      )
      const { user } = renderRoute('/login')
      const announcement = nextMessageInOtherTab()

      await user.type(await screen.findByLabelText('Email'), 'ada@example.com')
      await user.type(screen.getByLabelText('Password'), 'Sup3r-secret!')
      await user.click(screen.getByRole('button', { name: 'Log in' }))

      await expect(announcement).resolves.toBe(SESSION_CHANGED)
    })

    it('announces a logout', async () => {
      server.use(
        http.post(apiUrl('/users/auth/logout/'), () => new HttpResponse(null, { status: 205 })),
      )
      const { user } = renderRoute('/', { signedInAs: buildCurrentUser() })
      const announcement = nextMessageInOtherTab()

      await logOutViaAccountMenu(user)

      await expect(announcement).resolves.toBe(SESSION_CHANGED)
    })

    it('announces a password reset, which revokes every session', async () => {
      server.use(
        http.post(
          apiUrl('/users/auth/password-reset/confirm/'),
          () => new HttpResponse(null, { status: 200 }),
        ),
      )
      const { user } = renderRoute('/reset-password?uid=MQ&token=abc-123')
      const announcement = nextMessageInOtherTab()

      await user.type(await screen.findByLabelText('New password'), 'N3w-secret!')
      await user.type(screen.getByLabelText('Confirm new password'), 'N3w-secret!')
      await user.click(screen.getByRole('button', { name: 'Update password' }))

      await expect(announcement).resolves.toBe(SESSION_CHANGED)
    })
  })
})
