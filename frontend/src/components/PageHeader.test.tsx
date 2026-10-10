import { render, screen } from '@testing-library/react'

import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'

describe('PageHeader', () => {
  it('renders the title, description and actions, and titles the browser tab', () => {
    render(
      <PageHeader
        title="Projects"
        description="Everything your team is working on."
        actions={<Button>New project</Button>}
      />,
    )

    expect(screen.getByRole('heading', { level: 1, name: 'Projects' })).toBeInTheDocument()
    expect(screen.getByText('Everything your team is working on.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'New project' })).toBeInTheDocument()
    expect(document.title).toBe('Projects · DocSphere')
  })
})
