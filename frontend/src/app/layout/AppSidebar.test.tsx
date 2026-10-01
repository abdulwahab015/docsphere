import { screen, within } from '@testing-library/react'

import { buildCurrentUser } from '@/test/factories'
import { renderRoute } from '@/test/render'

function mainNavigation() {
  return within(screen.getByRole('navigation', { name: 'Main' }))
}

describe('AppSidebar', () => {
  it('shows admins the admin-only sections', () => {
    renderRoute('/', { signedInAs: buildCurrentUser({ org_role: 'ADMIN' }) })

    expect(mainNavigation().getByRole('link', { name: 'Organization' })).toBeInTheDocument()
  })

  it('hides admin-only sections from members', () => {
    renderRoute('/', { signedInAs: buildCurrentUser({ org_role: 'MEMBER' }) })

    expect(mainNavigation().getByRole('link', { name: 'People' })).toBeInTheDocument()
    expect(mainNavigation().queryByRole('link', { name: 'Organization' })).not.toBeInTheDocument()
  })

  it('marks the current section and navigates between sections', async () => {
    const { router, user } = renderRoute('/', { signedInAs: buildCurrentUser() })

    expect(mainNavigation().getByRole('link', { name: 'Projects' })).toHaveAttribute(
      'aria-current',
      'page',
    )

    await user.click(mainNavigation().getByRole('link', { name: 'People' }))

    expect(router.state.location.pathname).toBe('/people')
    expect(mainNavigation().getByRole('link', { name: 'People' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })
})
