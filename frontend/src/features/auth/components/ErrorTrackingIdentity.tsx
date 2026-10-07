import { useEffect } from 'react'

import type { CurrentUser } from '@/api/types'
import { errorTracking } from '@/lib/error-tracking'

/** Marks error reports with the signed-in user's and organization's ids while
 * it's shown, and with nobody once it's gone (signed out). Renders nothing. */
export function ErrorTrackingIdentity({ user }: { user: CurrentUser }) {
  useEffect(() => {
    errorTracking.identify(user)
    return () => errorTracking.identify(undefined)
  }, [user])

  return null
}
