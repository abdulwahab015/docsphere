import type { ActiveSubscription } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { ManageBillingButton } from '@/features/billing/components/ManageBillingButton'
import { INTERVAL_TITLES } from '@/features/billing/intervals'
import { formatLongDate } from '@/lib/format'

// A renewal payment failed and Stripe is retrying it; the plan still works.
const PAST_DUE = 'past_due'

function renewalText(subscription: ActiveSubscription) {
  if (subscription.status === PAST_DUE) {
    return 'Stripe is retrying the payment. Update your payment details to keep your access.'
  }
  if (!subscription.current_period_end) {
    return undefined
  }
  const date = formatLongDate(subscription.current_period_end)
  return subscription.cancel_at_period_end ? `Ends on ${date}` : `Renews on ${date}`
}

export function CurrentPlanCard({ subscription }: { subscription: ActiveSubscription }) {
  const interval = subscription.interval
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Your plan</h2>
        </CardTitle>
        <CardDescription>
          Change your plan, update payment details or cancel in the billing portal.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-3 text-sm">
        {subscription.status === PAST_DUE ? (
          <Badge variant="destructive">Payment failed</Badge>
        ) : (
          <Badge>Active</Badge>
        )}
        {interval && <span>{INTERVAL_TITLES[interval] ?? interval} plan</span>}
        <span className="text-muted-foreground">{renewalText(subscription)}</span>
      </CardContent>
      <CardFooter>
        <ManageBillingButton />
      </CardFooter>
    </Card>
  )
}
