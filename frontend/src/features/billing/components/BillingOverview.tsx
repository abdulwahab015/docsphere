import { ErrorState } from '@/components/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'
import { BillingEmailCard } from '@/features/billing/components/BillingEmailCard'
import { CurrentPlanCard } from '@/features/billing/components/CurrentPlanCard'
import { PlanPicker } from '@/features/billing/components/PlanPicker'
import { useOrganization } from '@/features/organization/hooks'

/** Everything about the organization's subscription: its current plan (or the
 * plans to choose from) and its billing email. Shared by the Billing page and
 * the screen a lapsed organization's admin sees. */
export function BillingOverview() {
  const organization = useOrganization()

  if (organization.isError) {
    return <ErrorState error={organization.error} onRetry={() => void organization.refetch()} />
  }
  if (!organization.data) {
    return <Skeleton className="h-64 w-full" aria-label="Loading billing" />
  }
  const { active_subscription: subscription, billing_email: billingEmail } = organization.data
  return (
    <div className="flex flex-col gap-6">
      {subscription ? (
        <CurrentPlanCard subscription={subscription} />
      ) : (
        <PlanPicker hasBillingEmail={Boolean(billingEmail)} />
      )}
      <BillingEmailCard organization={organization.data} />
    </div>
  )
}
