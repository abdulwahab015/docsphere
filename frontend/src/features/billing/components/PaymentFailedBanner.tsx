import { CreditCardIcon } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { useSignedInMember } from '@/features/auth/hooks'
import { ManageBillingButton } from '@/features/billing/components/ManageBillingButton'

/** Tells an admin, on every page, that a renewal payment failed. The
 * organization keeps its access while Stripe retries the card, so this warns
 * rather than locking anyone out; only admins can fix it, so only they see it. */
export function PaymentFailedBanner() {
  const user = useSignedInMember()
  if (user.org_role !== 'ADMIN' || !user.organization.payment_failed) {
    return null
  }

  return (
    <Alert variant="destructive">
      <CreditCardIcon />
      <AlertTitle>Your last payment failed</AlertTitle>
      <AlertDescription className="flex flex-col items-start gap-3">
        Stripe is retrying your card. Update your payment details so your organization keeps its
        access.
        <ManageBillingButton size="sm">Update payment details</ManageBillingButton>
      </AlertDescription>
    </Alert>
  )
}
