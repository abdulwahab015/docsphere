import { Outlet } from 'react-router'

import { AuthCard } from '@/features/auth/components/AuthCard'
import { LogoutButton } from '@/features/auth/components/LogoutButton'
import { useSignedInUser } from '@/features/auth/hooks'

const ADMIN_MESSAGE =
  "Your organization doesn't have an active subscription. Subscribe to a plan to start using DocSphere."
const MEMBER_MESSAGE =
  "Your organization doesn't have an active subscription. Ask your organization admin to renew it."

/** Mirrors the API's subscription gate, so an unpaid organization sees why
 * instead of a wall of 402 errors. Must sit inside `RequireAuth`. */
export function RequireActiveSubscription() {
  const user = useSignedInUser()

  if (user.organization.has_active_subscription) {
    return <Outlet />
  }

  return (
    <AuthCard
      title="Subscription inactive"
      description={user.org_role === 'ADMIN' ? ADMIN_MESSAGE : MEMBER_MESSAGE}
    >
      <LogoutButton className="w-full" />
    </AuthCard>
  )
}
