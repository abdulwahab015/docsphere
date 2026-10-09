import { lazy, Suspense } from 'react'
import { Outlet } from 'react-router'

import { FullPageSpinner } from '@/components/FullPageSpinner'
import { useSignedInUser } from '@/features/auth/hooks'

// Only people held by their organization's requirement ever see it, so its
// code (the QR code included) isn't part of what everyone downloads first.
const TwoFactorRequiredScreen = lazy(async () => ({
  default: (await import('@/features/two-factor/components/TwoFactorRequiredScreen'))
    .TwoFactorRequiredScreen,
}))

/** Mirrors the API's two-factor requirement: someone whose organization
 * requires two-factor sign-in, and who hasn't set it up, sets it up before
 * anything else - the API would refuse them everywhere. Must sit inside
 * `RequireAuth`. */
export function RequireTwoFactor() {
  const { organization, two_factor_enabled } = useSignedInUser()

  if (organization?.require_two_factor && !two_factor_enabled) {
    return (
      <Suspense fallback={<FullPageSpinner />}>
        <TwoFactorRequiredScreen organizationName={organization.name} />
      </Suspense>
    )
  }
  return <Outlet />
}
