import { useQueryClient } from '@tanstack/react-query'
import { Navigate, Outlet, useLocation } from 'react-router'

import { PATHS } from '@/app/paths'
import { ErrorTrackingIdentity } from '@/features/auth/components/ErrorTrackingIdentity'
import { SessionLoader } from '@/features/auth/components/SessionLoader'
import { returnState } from '@/features/auth/return-path'
import { wasSignedOutDeliberately } from '@/features/auth/session'
import { SignedInUserContext } from '@/features/auth/session-context'

/** Signed-in pages. A visitor without a session goes to the login page, which
 * sends them back here afterwards - except after a deliberate logout, when the
 * next person to sign in may be someone else. */
export function RequireAuth() {
  const location = useLocation()
  const queryClient = useQueryClient()

  return (
    <SessionLoader>
      {(user) =>
        user ? (
          <SignedInUserContext value={user}>
            <ErrorTrackingIdentity user={user} />
            <Outlet />
          </SignedInUserContext>
        ) : (
          <Navigate
            to={PATHS.login}
            state={wasSignedOutDeliberately(queryClient) ? undefined : returnState(location)}
            replace
          />
        )
      }
    </SessionLoader>
  )
}
