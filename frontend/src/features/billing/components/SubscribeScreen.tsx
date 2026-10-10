import { LogoutButton } from '@/features/auth/components/LogoutButton'
import { BillingOverview } from '@/features/billing/components/BillingOverview'
import { DeleteOrganizationCard } from '@/features/organization/components/DeleteOrganizationCard'

/** What a lapsed organization's admin sees in place of the app: the plans to
 * choose from and the billing email, since everything else is locked until
 * the organization subscribes - or, if it's leaving, deleting it. */
export function SubscribeScreen({ organizationName }: { organizationName: string }) {
  return (
    <main className="min-h-svh bg-muted px-4 py-10">
      <div className="mx-auto flex max-w-3xl flex-col gap-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <p className="text-lg font-semibold tracking-tight">DocSphere</p>
          <LogoutButton variant="outline" />
        </header>
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">Subscribe to continue</h1>
          <p className="text-muted-foreground">
            {organizationName} doesn&apos;t have an active subscription. Choose a plan to start
            using DocSphere; anything your organization already has is kept as it was.
          </p>
        </div>
        <BillingOverview />
        <DeleteOrganizationCard organizationName={organizationName} />
      </div>
    </main>
  )
}
