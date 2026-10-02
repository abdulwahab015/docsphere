import { apiClient } from '@/api/client'
import type {
  BillingPortalSessionResponse,
  CheckoutSessionResponse,
  Paginated,
  Price,
} from '@/api/types'

// Admin-only, and reachable without an active subscription - which is what
// they're for.
const SUBSCRIPTIONS_PATH = '/subscriptions/'

/** The plans on offer, cheapest first. */
export async function listPrices() {
  const { data } = await apiClient.get<Paginated<Price>>(`${SUBSCRIPTIONS_PATH}prices/`)
  return data
}

/** Starts Stripe Checkout for a plan; returns the hosted page to send the admin to. */
export async function startCheckout(priceId: string) {
  const { data } = await apiClient.post<CheckoutSessionResponse>(`${SUBSCRIPTIONS_PATH}checkout/`, {
    price_id: priceId,
  })
  return data.checkout_url
}

/** Opens Stripe's billing portal (payment details, invoices, cancelling). */
export async function openBillingPortal() {
  const { data } = await apiClient.post<BillingPortalSessionResponse>(
    `${SUBSCRIPTIONS_PATH}portal/`,
  )
  return data.portal_url
}
