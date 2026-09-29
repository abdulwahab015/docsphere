import { Navigate, Outlet, useLocation } from 'react-router'

import { PATHS } from '@/app/paths'
import { SessionLoader } from '@/features/auth/components/SessionLoader'
import { returnState } from '@/features/auth/return-path'

export function RequireAuth() {
  const location = useLocation()

  return (
    <SessionLoader>
      {(user) =>
        user ? <Outlet /> : <Navigate to={PATHS.login} state={returnState(location)} replace />
      }
    </SessionLoader>
  )
}
