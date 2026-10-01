import type { ActiveSubscription } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const INTERVAL_LABELS: Record<string, string> = { month: 'Monthly', year: 'Yearly' }

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'long' })

function renewalText(subscription: ActiveSubscription) {
  if (!subscription.current_period_end) {
    return undefined
  }
  const date = dateFormat.format(new Date(subscription.current_period_end))
  return subscription.cancel_at_period_end ? `Ends on ${date}` : `Renews on ${date}`
}

export function SubscriptionSummary({ subscription }: { subscription: ActiveSubscription | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Subscription</h2>
        </CardTitle>
        <CardDescription>Your organization&apos;s DocSphere plan.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-3 text-sm">
        {subscription ? (
          <>
            <Badge>Active</Badge>
            {subscription.interval && (
              <span>{INTERVAL_LABELS[subscription.interval] ?? subscription.interval} plan</span>
            )}
            <span className="text-muted-foreground">{renewalText(subscription)}</span>
          </>
        ) : (
          <Badge variant="outline">No active subscription</Badge>
        )}
      </CardContent>
    </Card>
  )
}
