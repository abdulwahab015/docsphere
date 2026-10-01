import { screen } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'

export async function logOutViaAccountMenu(user: UserEvent) {
  await user.click(screen.getByRole('button', { name: 'Account menu' }))
  await user.click(await screen.findByRole('menuitem', { name: 'Log out' }))
}
