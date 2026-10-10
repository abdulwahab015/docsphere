import { Link } from 'react-router'

import { PATHS } from '@/app/paths'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { AuthCard } from '@/features/auth/components/AuthCard'
import { useSubscriptionConfirmation } from '@/features/billing/hooks'

/** Where Stripe Checkout returns after payment. The subscription turns active
 * once Stripe tells the API (by webhook), so this waits for that. */
export function CheckoutSuccessPage() {
  const { isConfirmed, isTakingLong, checkAgain } = useSubscriptionConfirmation()

  if (isConfirmed) {
    return (
      <AuthCard
        title="You're subscribed"
        description="Thanks! Your organization's subscription is active."
        footer={
          <Button asChild className="w-full">
            <Link to={PATHS.home}>Start using DocSphere</Link>
          </Button>
        }
      />
    )
  }
  if (isTakingLong) {
    return (
      <AuthCard
        title="Still confirming your payment"
        description="Stripe hasn't confirmed it yet. This usually takes seconds, but can take a few minutes. If you paid, there's no need to pay again."
        footer={
          <Button variant="outline" className="w-full" onClick={checkAgain}>
            Check again
          </Button>
        }
      />
    )
  }
  return (
    <AuthCard
      title="Confirming your payment"
      description="Thanks! We're waiting for Stripe to confirm it - this page updates by itself."
    >
      <div className="flex justify-center">
        <Spinner aria-label="Waiting for confirmation" />
      </div>
    </AuthCard>
  )
}
