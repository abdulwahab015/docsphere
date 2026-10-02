import { PageHeader } from '@/components/PageHeader'
import { BillingOverview } from '@/features/billing/components/BillingOverview'

export function BillingPage() {
  return (
    <>
      <PageHeader title="Billing" description="Your organization's plan and billing details." />
      <BillingOverview />
    </>
  )
}
