import { BuildingIcon, FolderIcon, type LucideIcon, UsersIcon } from 'lucide-react'

import { PATHS } from '@/app/paths'

export interface NavItem {
  label: string
  path: string
  icon: LucideIcon
  /** Hidden from members; the route itself is also guarded by RequireOrgAdmin. */
  adminOnly?: boolean
}

export const NAV_ITEMS: NavItem[] = [
  { label: 'Projects', path: PATHS.projects, icon: FolderIcon },
  { label: 'People', path: PATHS.people, icon: UsersIcon },
  {
    label: 'Organization',
    path: PATHS.organizationSettings,
    icon: BuildingIcon,
    adminOnly: true,
  },
]
