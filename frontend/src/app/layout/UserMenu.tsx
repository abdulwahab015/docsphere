import { ChevronsUpDownIcon, LogOutIcon, UserRoundIcon } from 'lucide-react'
import { Link } from 'react-router'

import { PATHS } from '@/app/paths'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { SidebarMenuButton, useSidebar } from '@/components/ui/sidebar'
import { useLogout, useSignedInMember } from '@/features/auth/hooks'
import { ORG_ROLE_LABELS } from '@/lib/access'

export function UserMenu() {
  const user = useSignedInMember()
  const logout = useLogout()
  const { setOpenMobile } = useSidebar()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <SidebarMenuButton size="lg" aria-label="Account menu">
          <div className="grid flex-1 text-left text-sm leading-tight">
            <span className="truncate font-medium">{user.email}</span>
            <span className="truncate text-xs text-muted-foreground">
              {ORG_ROLE_LABELS[user.org_role]} · {user.organization.name}
            </span>
          </div>
          <ChevronsUpDownIcon className="ml-auto" aria-hidden />
        </SidebarMenuButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        side="top"
        align="start"
        className="w-(--radix-dropdown-menu-trigger-width)"
      >
        <DropdownMenuLabel className="truncate font-normal text-muted-foreground">
          {user.email}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {/* Closes the phone navigation drawer too, as the sidebar's links do. */}
        <DropdownMenuItem asChild onSelect={() => setOpenMobile(false)}>
          <Link to={PATHS.account}>
            <UserRoundIcon aria-hidden />
            Account settings
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem disabled={logout.isPending} onSelect={() => logout.mutate()}>
          <LogOutIcon aria-hidden />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
