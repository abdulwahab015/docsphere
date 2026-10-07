import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'

import { errorTracking } from '@/lib/error-tracking'
import { RouteErrorPage } from '@/pages/RouteErrorPage'

const pageError = new Error('Page failed to render')

function BrokenPage(): never {
  throw pageError
}

function renderBrokenPage() {
  const router = createMemoryRouter([
    { path: '/', element: <BrokenPage />, errorElement: <RouteErrorPage /> },
  ])
  render(<RouterProvider router={router} />)
}

describe('RouteErrorPage', () => {
  let report: ReturnType<typeof vi.spyOn>
  let consoleError: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    report = vi.spyOn(errorTracking, 'report').mockImplementation(() => {})
    // React logs the error the router caught; that's expected here.
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    report.mockRestore()
    consoleError.mockRestore()
  })

  it('reports the error that stopped the page', async () => {
    renderBrokenPage()

    expect(await screen.findByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument()
    expect(report).toHaveBeenCalledWith(pageError)
  })

  it('offers to reload the page', async () => {
    const reload = vi.fn<() => void>()
    const originalLocation = window.location
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...originalLocation, reload },
    })

    try {
      renderBrokenPage()
      await userEvent.click(await screen.findByRole('button', { name: 'Reload page' }))
    } finally {
      Object.defineProperty(window, 'location', { configurable: true, value: originalLocation })
    }

    expect(reload).toHaveBeenCalledTimes(1)
    expect(document.title).toBe('Something went wrong · DocSphere')
  })
})
