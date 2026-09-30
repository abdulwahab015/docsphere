import { Outlet } from 'react-router'

import { useSessionSyncAcrossTabs } from '@/features/auth/hooks'

/** Root layout route: every page stays in step with sign-ins and sign-outs
 * made in the app's other open tabs. */
export function SessionSyncLayout() {
  useSessionSyncAcrossTabs()
  return <Outlet />
}
