import type { ComponentProps } from 'react'

import { Button } from '@/components/ui/button'
import { useLogout } from '@/features/auth/hooks'

export function LogoutButton(buttonProps: ComponentProps<typeof Button>) {
  const logout = useLogout()

  return (
    <Button
      variant="outline"
      disabled={logout.isPending}
      onClick={() => logout.mutate()}
      {...buttonProps}
    >
      Log out
    </Button>
  )
}
