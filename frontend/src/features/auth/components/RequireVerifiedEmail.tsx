import { Outlet } from 'react-router'

import { VerifyEmailScreen } from '@/features/auth/components/VerifyEmailScreen'
import { useSignedInUser } from '@/features/auth/hooks'

/** Mirrors the API's verification gate: until a new signup follows the link
 * emailed to them, they're shown how to finish instead of the app, which
 * would refuse them everywhere. Must sit inside `RequireAuth`. */
export function RequireVerifiedEmail() {
  const user = useSignedInUser()

  return user.email_verified ? <Outlet /> : <VerifyEmailScreen email={user.email} />
}
