import {
  BuildingIcon,
  CreditCardIcon,
  FileTextIcon,
  FolderIcon,
  InboxIcon,
  type LucideIcon,
  UsersIcon,
} from 'lucide-react'

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
  { label: 'Documents', path: PATHS.documents, icon: FileTextIcon },
  { label: 'Requests', path: PATHS.accessRequests, icon: InboxIcon },
  { label: 'People', path: PATHS.people, icon: UsersIcon },
  {
    label: 'Organization',
    path: PATHS.organizationSettings,
    icon: BuildingIcon,
    adminOnly: true,
  },
  { label: 'Billing', path: PATHS.billing, icon: CreditCardIcon, adminOnly: true },
]
