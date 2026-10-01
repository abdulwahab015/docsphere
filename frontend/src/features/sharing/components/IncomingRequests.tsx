import { InboxIcon } from 'lucide-react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { documentPath } from '@/app/paths'
import { actionErrorMessage } from '@/api/errors'
import type { AccessRequest } from '@/api/types'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { Pagination } from '@/components/Pagination'
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
import type { AccessRequestDecision } from '@/features/sharing/api'
import { useIncomingAccessRequests, useReviewAccessRequest } from '@/features/sharing/hooks'
import { formatDate } from '@/lib/format'

const LOADING_ROWS = 3
const COLUMN_COUNT = 4

interface IncomingRequestsProps {
  page: number
  onPageChange: (page: number) => void
}

/** Pending requests on documents the signed-in user owns, to approve or deny. */
export function IncomingRequests({ page, onPageChange }: IncomingRequestsProps) {
  const requests = useIncomingAccessRequests(page)
  const review = useReviewAccessRequest()

  const decide = (accessRequest: AccessRequest, decision: AccessRequestDecision) => {
    const { requested_by_email: email, document_title: title } = accessRequest
    review.mutate(
      { accessRequest, decision },
      {
        onSuccess: () =>
          toast.success(
            decision === 'approve'
              ? `${email} can now edit "${title}".`
              : `Denied ${email}'s request for "${title}".`,
          ),
        onError: (error) =>
          toast.error(actionErrorMessage(error, `Couldn't answer ${email}'s request.`)),
      },
    )
  }

  const isDeciding = (accessRequest: AccessRequest, decision: AccessRequestDecision) =>
    review.isPending &&
    review.variables.accessRequest.id === accessRequest.id &&
    review.variables.decision === decision

  if (requests.isError) {
    return <ErrorState error={requests.error} onRetry={() => void requests.refetch()} />
  }
  if (requests.data && !requests.data.count) {
    return (
      <EmptyState
        icon={InboxIcon}
        title="Nothing to answer"
        description="When someone asks to edit a document you own, their request shows up here."
      />
    )
  }
  return (
    <>
      <div className="rounded-lg border">
        <Table aria-busy={requests.isFetching}>
          <TableHeader>
            <TableRow>
              <TableHead>Document</TableHead>
              <TableHead>Requested by</TableHead>
              <TableHead>Requested</TableHead>
              <TableHead>
                <span className="sr-only">Actions</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {requests.data
              ? requests.data.results.map((accessRequest) => (
                  <TableRow key={accessRequest.id}>
                    <TableCell className="font-medium">
                      <Link to={documentPath(accessRequest.document)} className="hover:underline">
                        {accessRequest.document_title}
                      </Link>
                    </TableCell>
                    <TableCell>{accessRequest.requested_by_email}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(accessRequest.created)}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          disabled={review.isPending}
                          onClick={() => decide(accessRequest, 'approve')}
                        >
                          {isDeciding(accessRequest, 'approve') && <Spinner aria-hidden />}
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={review.isPending}
                          onClick={() => decide(accessRequest, 'deny')}
                        >
                          {isDeciding(accessRequest, 'deny') && <Spinner aria-hidden />}
                          Deny
                        </Button>
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
      {requests.data && (
        <Pagination page={page} count={requests.data.count} onPageChange={onPageChange} />
      )}
    </>
  )
}
