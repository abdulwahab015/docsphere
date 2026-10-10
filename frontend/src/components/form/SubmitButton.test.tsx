import { render, screen } from '@testing-library/react'

import { SubmitButton } from '@/components/form/SubmitButton'

describe('SubmitButton', () => {
  it('is a ready submit button when idle', () => {
    render(<SubmitButton isPending={false}>Save</SubmitButton>)

    const button = screen.getByRole('button', { name: 'Save' })
    expect(button).toHaveAttribute('type', 'submit')
    expect(button).toBeEnabled()
  })

  it('shows progress and blocks double submits while pending', () => {
    render(<SubmitButton isPending>Save</SubmitButton>)

    expect(screen.getByRole('button', { name: /Save/ })).toBeDisabled()
    expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument()
  })
})
