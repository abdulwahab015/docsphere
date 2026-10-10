import { toast } from 'sonner'

import { actionErrorMessage } from '@/api/errors'
import type { OrganizationSummary } from '@/api/types'
import { Button } from '@/components/ui/button'
import { DeleteAccountDialog } from '@/features/account/components/DeleteAccountDialog'
import { AuthCard } from '@/features/auth/components/AuthCard'
import { LogoutButton } from '@/features/auth/components/LogoutButton'
import { useRestoreOrganization } from '@/features/organization/hooks'
import { formatDate } from '@/lib/format'

interface OrganizationDeletedScreenProps {
  organization: OrganizationSummary & { deletion_scheduled_for: string }
  isAdmin: boolean
}

/** What everyone in a deleted organization sees instead of the app, until
 * it's purged: when that happens, and - for its admins - a way to restore
 * it. Anyone may delete their own account here, which frees their email
 * address for another organization at once instead of at the purge. */
export function OrganizationDeletedScreen({
  organization,
  isAdmin,
}: OrganizationDeletedScreenProps) {
  const restore = useRestoreOrganization()
  const purgeDate = formatDate(organization.deletion_scheduled_for)

  const restoreOrganization = () =>
    restore.mutate(undefined, {
      onSuccess: () => toast.success(`Restored ${organization.name}.`),
      onError: (error) =>
        toast.error(actionErrorMessage(error, "Couldn't restore the organization. Try again.")),
    })

  return (
    <AuthCard
      title="Organization deleted"
      description={
        isAdmin
          ? `${organization.name} was deleted. It will be removed for good on ${purgeDate}, with everything in it. Until then you can restore it; you'll need to subscribe again. To use your email address elsewhere sooner, delete your account.`
          : `${organization.name} was deleted and will be removed for good on ${purgeDate}. Ask an admin if this is a mistake. To use your email address elsewhere sooner, delete your account.`
      }
    >
      <div className="flex flex-col gap-2">
        {isAdmin && (
          <Button disabled={restore.isPending} onClick={restoreOrganization}>
            Restore organization
          </Button>
        )}
        <DeleteAccountDialog triggerClassName="w-full" />
        <LogoutButton className="w-full" />
      </div>
    </AuthCard>
  )
}
