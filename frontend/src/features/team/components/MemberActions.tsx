import { EllipsisIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { actionErrorMessage } from '@/api/errors'
import type { UserDetail } from '@/api/types'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useChangeRole, useDeactivateUser } from '@/features/team/hooks'

type PendingAction = 'role' | 'deactivate'

/** An admin's menu for one member: switch them between admin and member, or
 * deactivate them - each confirmed first. Admins can't do either to
 * themselves (the API refuses), so the caller leaves this out of their row. */
export function MemberActions({ member }: { member: UserDetail }) {
  const [confirming, setConfirming] = useState<PendingAction | null>(null)
  const changeRole = useChangeRole()
  const deactivate = useDeactivateUser()
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
        description="They'll be signed out and can't log in until an admin reactivates them. What they've created and shared stays where it is."
        confirmLabel="Deactivate"
        destructive
        onConfirm={deactivateMember}
        isPending={deactivate.isPending}
      />
    </>
  )
}
