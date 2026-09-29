import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'

import { routes } from '@/app/routes'

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(<RouterProvider router={router} />)
  return router
}

describe('routes', () => {
  it('renders the home page at the root path', () => {
    renderAt('/')

    expect(screen.getByRole('heading', { name: 'DocSphere' })).toBeInTheDocument()
  })

  it('renders the not-found page for an unknown path', () => {
    renderAt('/does-not-exist')

    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })

  it('navigates home from the not-found page', async () => {
    const router = renderAt('/does-not-exist')

    await userEvent.click(screen.getByRole('link', { name: 'Go home' }))

    expect(router.state.location.pathname).toBe('/')
    expect(screen.getByRole('heading', { name: 'DocSphere' })).toBeInTheDocument()
  })
})
