import { render, screen } from '@testing-library/react'

import { PersonLabel } from '@/components/PersonLabel'

describe('PersonLabel', () => {
  it('shows the name, with the email address beneath it', () => {
    render(<PersonLabel person={{ name: 'Grace Hopper', email: 'grace@example.com' }} />)

    expect(screen.getByText('Grace Hopper')).toBeInTheDocument()
    expect(screen.getByText('grace@example.com')).toBeInTheDocument()
  })

  it("shows the email address alone while there's no name", () => {
    const { container } = render(<PersonLabel person={{ name: '', email: 'grace@example.com' }} />)

    expect(container).toHaveTextContent(/^grace@example\.com$/)
  })

  it('adds a note after the name', () => {
    const { container } = render(
      <PersonLabel person={{ name: 'Grace Hopper', email: 'grace@example.com' }} note="(you)" />,
    )

    expect(container).toHaveTextContent('Grace Hopper (you)grace@example.com')
  })
})
