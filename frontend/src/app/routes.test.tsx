import { screen } from '@testing-library/react'

import { buildCurrentUser } from '@/test/factories'
import { renderRoute } from '@/test/render'

describe('routes', () => {
  it('shows the home page to a signed-in user', () => {
    renderRoute('/', { signedInAs: buildCurrentUser() })

    expect(screen.getByText(/Signed in as ada@example.com · Acme/)).toBeInTheDocument()
  })

  it('sends a signed-out visitor to the login page', async () => {
    const { router } = renderRoute('/')

    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
  })

  it('sends a signed-in user away from the login page', () => {
    const { router } = renderRoute('/login', { signedInAs: buildCurrentUser() })

    expect(router.state.location.pathname).toBe('/')
  })

  it('renders the not-found page for an unknown path', () => {
    renderRoute('/does-not-exist')

    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })

  it('navigates home from the not-found page', async () => {
    const { router, user } = renderRoute('/does-not-exist', { signedInAs: buildCurrentUser() })

    await user.click(screen.getByRole('link', { name: 'Go home' }))

    expect(router.state.location.pathname).toBe('/')
  })
})
