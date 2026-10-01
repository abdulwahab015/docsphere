import { Outlet } from 'react-router'

import { ForbiddenState } from '@/components/ErrorState'
import { useSignedInMember } from '@/features/auth/hooks'

/** Admin-only pages. The API enforces the same rule; this just shows members
 * why there's nothing here instead of a failing request. Must sit inside
 * `RequireActiveSubscription`. */
export function RequireOrgAdmin() {
  const user = useSignedInMember()
  return user.org_role === 'ADMIN' ? <Outlet /> : <ForbiddenState />
}
