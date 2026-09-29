import { render, screen } from '@testing-library/react'

import { App } from '@/app/App'

describe('App', () => {
  it('mounts the router inside the app providers', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'DocSphere' })).toBeInTheDocument()
  })
})
