import { MailIcon } from 'lucide-react'
import { type ComponentProps, useState } from 'react'
import { toast } from 'sonner'

import { actionErrorMessage } from '@/api/errors'
import type { Invitation, InvitationStatus } from '@/api/types'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { Pagination } from '@/components/Pagination'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useInvitations, useResendInvitation, useRevokeInvitation } from '@/features/team/hooks'
import { useListParams } from '@/hooks/use-list-params'
import { formatDate } from '@/lib/format'
import { SECONDARY_COLUMN } from '@/lib/table-columns'
import { cn } from '@/lib/utils'

const LOADING_ROWS = 3
const COLUMN_COUNT = 5

const STATUS_LABELS: Record<InvitationStatus, string> = {
  PENDING: 'Pending',
  ACCEPTED: 'Accepted',
  EXPIRED: 'Expired',
  REVOKED: 'Revoked',
}

const STATUS_VARIANTS: Record<InvitationStatus, ComponentProps<typeof Badge>['variant']> = {
  PENDING: 'secondary',
  ACCEPTED: 'default',
  EXPIRED: 'outline',
  REVOKED: 'outline',
}

/** Every invitation the organization has sent, newest first. A pending one can
 * be resent or revoked; an expired one resent (with a fresh link). */
export function InvitationList() {
  const { page, setPage } = useListParams()
  const invitations = useInvitations(page)
  const resend = useResendInvitation()
  const revoke = useRevokeInvitation()
  const [revoking, setRevoking] = useState<Invitation | null>(null)

  const resendInvitation = ({ id, email }: Invitation) =>
    resend.mutate(id, {
      onSuccess: () =>
        toast.success(`Sent a new invitation to ${email}. The earlier link no longer works.`),
      onError: (error) => toast.error(actionErrorMessage(error, `Couldn't resend to ${email}.`)),
    })

  const revokeInvitation = ({ id, email }: Invitation) =>
    revoke.mutate(id, {
      onSuccess: () => {
        toast.success(`Revoked the invitation to ${email}.`)
        setRevoking(null)
      },
      onError: (error) => {
        toast.error(actionErrorMessage(error, `Couldn't revoke the invitation to ${email}.`))
        setRevoking(null)
      },
    })

  if (invitations.isError) {
    return <ErrorState error={invitations.error} onRetry={() => void invitations.refetch()} />
  }
  if (invitations.data && !invitations.data.count) {
    return (
      <EmptyState
        icon={MailIcon}
        title="No invitations yet"
        description="Invite people by email, or upload a spreadsheet of addresses."
      />
    )
  }
  return (
    <>
      <div className="rounded-lg border">
        <Table aria-busy={invitations.isFetching}>
          <TableHeader>
            <TableRow>
              <TableHead>Email</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className={SECONDARY_COLUMN}>Invited by</TableHead>
              <TableHead className={SECONDARY_COLUMN}>Sent</TableHead>
              <TableHead>
                <span className="sr-only">Actions</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {invitations.data
              ? invitations.data.results.map((invitation) => (
                  <TableRow key={invitation.id}>
                    <TableCell className="font-medium">{invitation.email}</TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANTS[invitation.status]}>
                        {STATUS_LABELS[invitation.status]}
                      </Badge>
                    </TableCell>
                    <TableCell className={cn(SECONDARY_COLUMN, 'text-muted-foreground')}>
                      {invitation.invited_by_email ?? '—'}
                    </TableCell>
                    <TableCell className={cn(SECONDARY_COLUMN, 'text-muted-foreground')}>
                      {formatDate(invitation.sent_at)}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-2">
                        {(invitation.status === 'PENDING' || invitation.status === 'EXPIRED') && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={resend.isPending}
                            onClick={() => resendInvitation(invitation)}
                          >
                            {resend.isPending && resend.variables === invitation.id && (
                              <Spinner aria-hidden />
                            )}
                            Resend
                          </Button>
                        )}
                        {invitation.status === 'PENDING' && (
                          <Button size="sm" variant="ghost" onClick={() => setRevoking(invitation)}>
                            Revoke
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              : Array.from({ length: LOADING_ROWS }, (_unused, index) => (
                  <TableRow key={index}>
                    <TableCell colSpan={COLUMN_COUNT}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
      </div>
      {invitations.data && (
        <Pagination page={page} count={invitations.data.count} onPageChange={setPage} />
      )}
      {revoking && (
        <ConfirmDialog
          open
          // There's no trigger: the dialog opens from a row's button, so it only ever closes.
          onOpenChange={() => setRevoking(null)}
          title={`Revoke the invitation to ${revoking.email}?`}
          description="The link in their email will stop working. You can invite them again later."
          confirmLabel="Revoke"
          destructive
          onConfirm={() => revokeInvitation(revoking)}
          isPending={revoke.isPending}
        />
      )}
    </>
  )
}
