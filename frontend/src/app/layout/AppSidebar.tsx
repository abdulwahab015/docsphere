import { FileTextIcon } from 'lucide-react'
import { Link, NavLink, useMatch } from 'react-router'

import { NAV_ITEMS, type NavItem } from '@/app/navigation'
import { PATHS } from '@/app/paths'
import { UserMenu } from '@/app/layout/UserMenu'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from '@/components/ui/sidebar'
import { useSignedInMember } from '@/features/auth/hooks'

function NavItemLink({ item }: { item: NavItem }) {
  // A section stays active on its sub-pages (e.g. a project's own page).
  const isActive = Boolean(useMatch({ path: item.path, end: false }))
  const { setOpenMobile } = useSidebar()

  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild isActive={isActive} tooltip={item.label}>
        {/* On a phone the navigation is a drawer over the page; close it once a
            destination is picked. (A no-op on larger screens.) */}
        <NavLink to={item.path} onClick={() => setOpenMobile(false)}>
          <item.icon aria-hidden />
          <span>{item.label}</span>
        </NavLink>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

export function AppSidebar() {
  const user = useSignedInMember()
  const isAdmin = user.org_role === 'ADMIN'
  const items = NAV_ITEMS.filter((item) => isAdmin || !item.adminOnly)

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link to={PATHS.projects}>
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                  <FileTextIcon className="size-4" aria-hidden />
                </div>
                <span className="font-semibold">DocSphere</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <nav aria-label="Main">
              <SidebarMenu>
                {items.map((item) => (
                  <NavItemLink key={item.path} item={item} />
                ))}
              </SidebarMenu>
            </nav>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <UserMenu />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
