import { ErrorState } from '@/components/ErrorState'
import { PageHeader } from '@/components/PageHeader'
import { Skeleton } from '@/components/ui/skeleton'
import { OrganizationSettingsForm } from '@/features/organization/components/OrganizationSettingsForm'
import { useOrganization } from '@/features/organization/hooks'

export function OrganizationSettingsPage() {
  const organization = useOrganization()

  return (
    <>
      <PageHeader title="Organization" description="Manage your organization's details." />
      {organization.isError ? (
        <ErrorState error={organization.error} onRetry={() => void organization.refetch()} />
      ) : organization.data ? (
        <OrganizationSettingsForm organization={organization.data} />
      ) : (
        <Skeleton className="h-64 w-full" aria-label="Loading organization" />
      )}
    </>
  )
}
