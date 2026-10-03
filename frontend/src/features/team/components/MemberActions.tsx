import { EllipsisIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { actionErrorMessage } from '@/api/errors'
import type { SoleOwnership, UserDetail } from '@/api/types'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useChangeRole, useDeactivateUser, useSoleOwnership } from '@/features/team/hooks'

type PendingAction = 'role' | 'deactivate'

function countOf(count: number, noun: string) {
  return `${count} ${noun}${count === 1 ? '' : 's'}`
}

/** Warns that what only this member owns would be left with nobody able to
 * manage its sharing; nothing when they share ownership of everything. */
function soleOwnershipWarning({ projects, documents }: SoleOwnership) {
  const owned = [
    projects && countOf(projects, 'project'),
    documents && countOf(documents, 'document'),
  ].filter(Boolean)
  if (!owned.length) {
    return null
  }
  return `They're the only Owner of ${owned.join(' and ')}. Nobody can change who has access to those until they're reactivated.`
}

/** An admin's menu for one member: switch them between admin and member, or
 * deactivate them - each confirmed first. Admins can't do either to
 * themselves (the API refuses), so the caller leaves this out of their row. */
export function MemberActions({ member }: { member: UserDetail }) {
  const [confirming, setConfirming] = useState<PendingAction | null>(null)
  const changeRole = useChangeRole()
  const deactivate = useDeactivateUser()
  const soleOwnership = useSoleOwnership(member.id, { enabled: confirming === 'deactivate' })
  const ownershipWarning = soleOwnership.data && soleOwnershipWarning(soleOwnership.data)
  const { email } = member
  const isAdmin = member.org_role === 'ADMIN'

  const close = () => setConfirming(null)
  const reportFailure = (fallback: string) => (error: unknown) => {
    toast.error(actionErrorMessage(error, fallback))
    close()
  }

  const switchRole = () =>
    changeRole.mutate(
      { userId: member.id, orgRole: isAdmin ? 'MEMBER' : 'ADMIN' },
      {
        onSuccess: (updated) => {
          toast.success(
            `${email} is now ${updated.org_role === 'ADMIN' ? 'an admin' : 'a member'}.`,
          )
          close()
        },
        onError: reportFailure(`Couldn't change ${email}'s role.`),
      },
    )

  const deactivateMember = () =>
    deactivate.mutate(member.id, {
      onSuccess: () => {
        toast.success(`Deactivated ${email}.`)
        close()
      },
      onError: reportFailure(`Couldn't deactivate ${email}.`),
    })

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${email}`}>
            <EllipsisIcon aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => setConfirming('role')}>
            {isAdmin ? 'Make member' : 'Make admin'}
          </DropdownMenuItem>
          <DropdownMenuItem variant="destructive" onSelect={() => setConfirming('deactivate')}>
            Deactivate
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <ConfirmDialog
        open={confirming === 'role'}
        onOpenChange={close}
        title={isAdmin ? `Make ${email} a member?` : `Make ${email} an admin?`}
        description={
          isAdmin
            ? "They'll no longer be able to manage people, billing or organization settings."
            : 'Admins manage people, invitations, billing and organization settings, and create projects.'
        }
        confirmLabel={isAdmin ? 'Make member' : 'Make admin'}
        onConfirm={switchRole}
        isPending={changeRole.isPending}
      />
      <ConfirmDialog
        open={confirming === 'deactivate'}
        onOpenChange={close}
        title={`Deactivate ${email}?`}
        description={
          <>
            They&apos;ll be signed out and can&apos;t log in until an admin reactivates them. What
            they&apos;ve created and shared stays where it is.
            {ownershipWarning && (
              <span className="mt-2 block font-medium text-foreground">{ownershipWarning}</span>
            )}
          </>
        }
        confirmLabel="Deactivate"
        destructive
        onConfirm={deactivateMember}
        isPending={deactivate.isPending}
      />
    </>
  )
}
