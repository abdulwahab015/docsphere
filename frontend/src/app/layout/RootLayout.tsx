import { Outlet } from 'react-router'

import { Toaster } from '@/components/ui/sonner'
import { useSessionSyncAcrossTabs } from '@/features/auth/hooks'

/** Wraps every route: keeps this tab's session in step with the app's other
 * open tabs, and hosts the toast notifications. */
export function RootLayout() {
  useSessionSyncAcrossTabs()

  return (
    <>
      <Outlet />
      <Toaster />
    </>
  )
}
