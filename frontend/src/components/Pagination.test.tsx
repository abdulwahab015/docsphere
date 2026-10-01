import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Pagination } from '@/components/Pagination'

describe('Pagination', () => {
  it('shows the range on the current page and moves between pages', async () => {
    const onPageChange = vi.fn<(page: number) => void>()
    render(<Pagination page={2} count={45} onPageChange={onPageChange} />)

    expect(screen.getByText('Showing 21–40 of 45')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await userEvent.click(screen.getByRole('button', { name: 'Previous' }))

    expect(onPageChange.mock.calls).toEqual([[3], [1]])
  })

  it('disables moving past the first and last pages', () => {
    const { rerender } = render(<Pagination page={1} count={45} onPageChange={() => {}} />)
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()

    rerender(<Pagination page={3} count={45} onPageChange={() => {}} />)
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
    expect(screen.getByText('Showing 41–45 of 45')).toBeInTheDocument()
  })

  it('honours a custom page size', () => {
    render(<Pagination page={1} count={12} pageSize={5} onPageChange={() => {}} />)

    expect(screen.getByText('Showing 1–5 of 12')).toBeInTheDocument()
    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
  })

  it('hides the page controls when everything fits on one page', () => {
    render(<Pagination page={1} count={0} onPageChange={() => {}} />)

    expect(screen.getByText('No results')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
