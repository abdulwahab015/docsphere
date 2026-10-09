import { ErrorState } from '@/components/ErrorState'
import { PageHeader } from '@/components/PageHeader'
import { Skeleton } from '@/components/ui/skeleton'
import { DeleteOrganizationCard } from '@/features/organization/components/DeleteOrganizationCard'
import { ExportDataCard } from '@/features/organization/components/ExportDataCard'
import { OrganizationSettingsForm } from '@/features/organization/components/OrganizationSettingsForm'
import { useOrganization } from '@/features/organization/hooks'

export function OrganizationSettingsPage() {
  const organization = useOrganization()

  return (
    <>
      <PageHeader
        title="Organization"
        description="Manage your organization's details, export its data or delete it."
      />
      {organization.isError ? (
        <ErrorState error={organization.error} onRetry={() => void organization.refetch()} />
      ) : organization.data ? (
        <div className="flex flex-col gap-6">
          <OrganizationSettingsForm organization={organization.data} />
          <ExportDataCard />
          <DeleteOrganizationCard organizationName={organization.data.name} />
        </div>
      ) : (
        <Skeleton className="h-64 w-full" aria-label="Loading organization" />
      )}
    </>
  )
}
