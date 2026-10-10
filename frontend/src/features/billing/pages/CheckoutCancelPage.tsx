import { Link } from 'react-router'

import { PATHS } from '@/app/paths'
import { Button } from '@/components/ui/button'
import { AuthCard } from '@/features/auth/components/AuthCard'

/** Where Stripe Checkout returns when the admin backs out. */
export function CheckoutCancelPage() {
  return (
    <AuthCard
      title="Checkout cancelled"
      description="You haven't been charged. You can pick a plan whenever you're ready."
      footer={
        <Button asChild className="w-full">
          <Link to={PATHS.billing}>Back to billing</Link>
        </Button>
      }
    />
  )
}
