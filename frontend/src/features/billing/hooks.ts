import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import type { CurrentUser } from '@/api/types'
import { authKeys } from '@/features/auth/query-keys'
import { loadSession } from '@/features/auth/session'
import { listPrices, openBillingPortal, startCheckout } from '@/features/billing/api'
import { billingKeys } from '@/features/billing/query-keys'
import { organizationKeys } from '@/features/organization/query-keys'
import { externalRedirect } from '@/lib/external-redirect'

/** How often, and for how long, the return-from-checkout page asks whether
 * the subscription is active yet. Stripe confirms payment to the API by
 * webhook, usually within seconds. */
export const CONFIRMATION_POLL_MS = 2_000
export const CONFIRMATION_TIMEOUT_MS = 60_000

export function usePrices() {
  return useQuery({ queryKey: billingKeys.prices, queryFn: listPrices })
}

/** Sends the admin to Stripe Checkout for a plan. Stays pending-looking after
 * success, since the page is about to unload. */
export function useStartCheckout() {
  return useMutation({
    mutationFn: startCheckout,
    onSuccess: (checkoutUrl) => externalRedirect.to(checkoutUrl),
  })
}

export function useOpenBillingPortal() {
  return useMutation({
    mutationFn: openBillingPortal,
    onSuccess: (portalUrl) => externalRedirect.to(portalUrl),
  })
}

function hasActiveSubscription(user: CurrentUser | null | undefined) {
  return Boolean(user?.organization?.has_active_subscription)
}

/**
 * After Stripe Checkout, waits for the subscription to become active: the
 * session (which carries `has_active_subscription`) is re-read every
 * `CONFIRMATION_POLL_MS` until it is, or until `CONFIRMATION_TIMEOUT_MS` has
 * passed. `checkAgain` restarts the wait. Sharing the session's query means
 * the rest of the app unlocks the moment it's confirmed.
 */
export function useSubscriptionConfirmation() {
  const queryClient = useQueryClient()
  const [waitingSince, setWaitingSince] = useState(Date.now)
  const session = useQuery({
    queryKey: authKeys.currentUser,
    queryFn: loadSession,
    refetchInterval: (query) =>
      hasActiveSubscription(query.state.data) ||
      query.state.dataUpdatedAt - waitingSince >= CONFIRMATION_TIMEOUT_MS
        ? false
        : CONFIRMATION_POLL_MS,
  })
  const isConfirmed = hasActiveSubscription(session.data)

  // The organization's profile, cached from before checkout, shows the new plan too.
  useEffect(() => {
    if (isConfirmed) {
      void queryClient.invalidateQueries({ queryKey: organizationKeys.profile })
    }
  }, [isConfirmed, queryClient])

  const checkAgain = () => {
    setWaitingSince(Date.now())
    void session.refetch()
  }

  return {
    isConfirmed,
    isTakingLong: !isConfirmed && session.dataUpdatedAt - waitingSince >= CONFIRMATION_TIMEOUT_MS,
    checkAgain,
  }
}
