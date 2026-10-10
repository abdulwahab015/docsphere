import { screen } from '@testing-library/react'

import { buildCurrentUser } from '@/test/factories'
import { renderRoute } from '@/test/render'

describe('routes', () => {
  it('opens a signed-in user on their projects', async () => {
    const { router } = renderRoute('/', { signedInAs: buildCurrentUser() })

    expect(await screen.findByRole('heading', { level: 1, name: 'Projects' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/projects')
  })

  it('sends a signed-out visitor to the login page', async () => {
    const { router } = renderRoute('/')

    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
  })

  it('sends a signed-in user away from the login page', () => {
    const { router } = renderRoute('/login', { signedInAs: buildCurrentUser() })

    expect(router.state.location.pathname).toBe('/projects')
  })

  it('renders the not-found page for an unknown path', () => {
    renderRoute('/does-not-exist')

    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })

  it("shows a spinner while the first page's code loads, then the page", async () => {
    const { user } = renderRoute('/does-not-exist', {
      signedInAs: buildCurrentUser(),
      loadPagesOnDemand: true,
    })

    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    await user.click(await screen.findByRole('link', { name: 'Go home' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Projects' })).toBeInTheDocument()
  })

  it('navigates home from the not-found page', async () => {
    const { router, user } = renderRoute('/does-not-exist', { signedInAs: buildCurrentUser() })

    await user.click(screen.getByRole('link', { name: 'Go home' }))

    expect(router.state.location.pathname).toBe('/projects')
  })
})
