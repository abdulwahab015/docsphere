import { createContext } from 'react'

import type { CurrentUser, OrganizationSummary } from '@/api/types'

export type OrganizationMember = CurrentUser & { organization: OrganizationSummary }

// Provided by the route guards rather than read from the query cache by each
// component: a component that re-renders for its own reason while the
// session is ending (e.g. the menu that ran the logout) then still sees the
// user its guard rendered it with, instead of an already-cleared session.
export const SignedInUserContext = createContext<CurrentUser | null>(null)
export const OrganizationMemberContext = createContext<OrganizationMember | null>(null)
