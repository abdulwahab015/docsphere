import { lazy, Suspense } from 'react'
import { Outlet } from 'react-router'

import { FullPageSpinner } from '@/components/FullPageSpinner'
import { AuthCard } from '@/features/auth/components/AuthCard'
import { LogoutButton } from '@/features/auth/components/LogoutButton'
import { useSignedInUser } from '@/features/auth/hooks'
import { OrganizationMemberContext } from '@/features/auth/session-context'

// Only a lapsed organization's admin ever sees it, so its code (the plans and
// the billing email form) isn't part of what everyone downloads first.
const SubscribeScreen = lazy(async () => ({
  default: (await import('@/features/billing/components/SubscribeScreen')).SubscribeScreen,
}))

const NO_ORGANIZATION_MESSAGE =
  "This account isn't part of an organization. Platform administrators manage DocSphere from the admin site."
const MEMBER_MESSAGE =
  "Your organization doesn't have an active subscription. Ask your organization admin to renew it."

/** Mirrors the API's subscription gate, so an unpaid organization sees why
 * instead of a wall of 402 errors - and its admin can subscribe right there.
 * Also turns away accounts that belong to no organization (platform
 * superusers), which the app has nothing to show. Must sit inside
 * `RequireAuth`. */
export function RequireActiveSubscription() {
  const user = useSignedInUser()
  const { organization } = user

  if (!organization) {
    return <BlockedScreen title="No organization" message={NO_ORGANIZATION_MESSAGE} />
  }
  if (!organization.has_active_subscription) {
    return user.org_role === 'ADMIN' ? (
      <Suspense fallback={<FullPageSpinner />}>
        <SubscribeScreen organizationName={organization.name} />
      </Suspense>
    ) : (
      <BlockedScreen title="Subscription inactive" message={MEMBER_MESSAGE} />
    )
  }
  return (
    <OrganizationMemberContext value={{ ...user, organization }}>
      <Outlet />
    </OrganizationMemberContext>
  )
}

function BlockedScreen({ title, message }: { title: string; message: string }) {
  return (
    <AuthCard title={title} description={message}>
      <LogoutButton className="w-full" />
    </AuthCard>
  )
}
