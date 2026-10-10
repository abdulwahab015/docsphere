import { CreditCardIcon } from 'lucide-react'
import { useId } from 'react'
import { toast } from 'sonner'

import { actionErrorMessage } from '@/api/errors'
import type { Price } from '@/api/types'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { ManageBillingButton } from '@/features/billing/components/ManageBillingButton'
import { usePrices, useStartCheckout } from '@/features/billing/hooks'
import { INTERVAL_PERIODS, INTERVAL_TITLES } from '@/features/billing/intervals'
import { formatMoney } from '@/lib/format'

interface PlanPickerProps {
  /** Checkout needs a billing email; without one, plans are shown but can't be bought. */
  hasBillingEmail: boolean
}

/** The plans on offer, each with a Subscribe button that starts Stripe Checkout. */
export function PlanPicker({ hasBillingEmail }: PlanPickerProps) {
  const headingId = useId()
  const prices = usePrices()
  const checkout = useStartCheckout()

  const subscribe = (price: Price) =>
    checkout.mutate(price.id, {
      onError: (error) => toast.error(actionErrorMessage(error, "Couldn't start checkout.")),
    })

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 id={headingId} className="text-lg font-semibold">
          Choose a plan
        </h2>
        <p className="text-sm text-muted-foreground">
          {hasBillingEmail
            ? "You'll pay securely on Stripe, then come straight back here."
            : 'Add a billing email below before subscribing - invoices are sent there.'}
        </p>
      </div>
      {prices.isError ? (
        <ErrorState error={prices.error} onRetry={() => void prices.refetch()} />
      ) : !prices.data ? (
        <Skeleton className="h-40 w-full" aria-label="Loading plans" />
      ) : !prices.data.results.length ? (
        <EmptyState
          icon={CreditCardIcon}
          title="No plans available"
          description="No plans are on offer yet. Please try again later."
        />
      ) : (
        <ul aria-label="Plans" className="grid gap-4 sm:grid-cols-2">
          {prices.data.results.map((price) => {
            // Still busy after success: the browser is on its way to Stripe.
            const isLeaving =
              (checkout.isPending || checkout.isSuccess) && checkout.variables === price.id
            const title = (price.interval && INTERVAL_TITLES[price.interval]) || price.product_name
            return (
              <li key={price.id}>
                <Card className="h-full">
                  <CardHeader>
                    <CardTitle>
                      <h3>{title}</h3>
                    </CardTitle>
                    <CardDescription>{price.product_name}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {price.unit_amount !== null && (
                      <p className="text-2xl font-semibold">
                        {formatMoney(price.unit_amount, price.currency)}
                        {price.interval && (
                          <span className="text-sm font-normal text-muted-foreground">
                            {' '}
                            {INTERVAL_PERIODS[price.interval] ?? `per ${price.interval}`}
                          </span>
                        )}
                      </p>
                    )}
                  </CardContent>
                  <CardFooter>
                    <Button
                      className="w-full"
                      aria-label={`Subscribe to the ${title.toLowerCase()} plan`}
                      disabled={!hasBillingEmail || checkout.isPending || checkout.isSuccess}
                      onClick={() => subscribe(price)}
                    >
                      {isLeaving && <Spinner aria-hidden />}
                      Subscribe
                    </Button>
                  </CardFooter>
                </Card>
              </li>
            )
          })}
        </ul>
      )}
      <p className="text-sm text-muted-foreground">
        Subscribed before?{' '}
        <ManageBillingButton variant="link" className="h-auto p-0">
          Update your payment details in the billing portal.
        </ManageBillingButton>
      </p>
    </section>
  )
}
