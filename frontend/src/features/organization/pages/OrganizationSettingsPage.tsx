import { ErrorState } from '@/components/ErrorState'
import { PageHeader } from '@/components/PageHeader'
import { Skeleton } from '@/components/ui/skeleton'
import { OrganizationSettingsForm } from '@/features/organization/components/OrganizationSettingsForm'
import { SubscriptionSummary } from '@/features/organization/components/SubscriptionSummary'
import { useOrganization } from '@/features/organization/hooks'

export function OrganizationSettingsPage() {
  const organization = useOrganization()

  return (
    <>
      <PageHeader title="Organization" description="Manage your organization's details." />
      {organization.isError ? (
        <ErrorState error={organization.error} onRetry={() => void organization.refetch()} />
      ) : organization.data ? (
        <div className="flex flex-col gap-6">
          <OrganizationSettingsForm organization={organization.data} />
          <SubscriptionSummary subscription={organization.data.active_subscription} />
        </div>
      ) : (
        <Skeleton className="h-64 w-full" aria-label="Loading organization" />
      )}
    </>
  )
}
