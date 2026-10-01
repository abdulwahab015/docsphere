import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { RouteErrorPage } from '@/pages/RouteErrorPage'

describe('RouteErrorPage', () => {
  it('offers to reload the page', async () => {
    const reload = vi.fn<() => void>()
    const originalLocation = window.location
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...originalLocation, reload },
    })

    try {
      render(<RouteErrorPage />)
      await userEvent.click(screen.getByRole('button', { name: 'Reload page' }))
    } finally {
      Object.defineProperty(window, 'location', { configurable: true, value: originalLocation })
    }

    expect(reload).toHaveBeenCalledTimes(1)
    expect(document.title).toBe('Something went wrong · DocSphere')
  })
})
