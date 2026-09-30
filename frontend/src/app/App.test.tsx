import { render, screen } from '@testing-library/react'

import { App } from '@/app/App'

describe('App', () => {
  it('mounts the router inside the app providers', async () => {
    render(<App />)

    // Nobody is signed in, so the root path redirects to the login page.
    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
  })
})
