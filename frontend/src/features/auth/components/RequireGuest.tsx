import { Navigate, Outlet, useLocation } from 'react-router'

import { SessionLoader } from '@/features/auth/components/SessionLoader'
import { getReturnPath } from '@/features/auth/return-path'

/** For signed-out-only pages (login, signup). Once a session exists - including
 * one just started on this page - it sends the user on to where they were
 * headed before being asked to log in. */
export function RequireGuest() {
  const location = useLocation()

  return (
    <SessionLoader>
      {(user) => (user ? <Navigate to={getReturnPath(location.state)} replace /> : <Outlet />)}
    </SessionLoader>
  )
}
