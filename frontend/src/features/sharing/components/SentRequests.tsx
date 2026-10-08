import { SendIcon } from 'lucide-react'
import { Link } from 'react-router'

import { documentPath } from '@/app/paths'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { Pagination } from '@/components/Pagination'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { AccessRequestStatusBadge } from '@/features/sharing/components/AccessRequestStatusBadge'
import { useMyAccessRequests } from '@/features/sharing/hooks'
import { formatDate } from '@/lib/format'
import { displayName } from '@/lib/people'
import { SECONDARY_COLUMN } from '@/lib/table-columns'
import { cn } from '@/lib/utils'

const LOADING_ROWS = 3
const COLUMN_COUNT = 4

interface SentRequestsProps {
  page: number
  onPageChange: (page: number) => void
}

/** The signed-in user's own requests, newest first, and how each was answered. */
export function SentRequests({ page, onPageChange }: SentRequestsProps) {
  const requests = useMyAccessRequests(page)

  if (requests.isError) {
    return <ErrorState error={requests.error} onRetry={() => void requests.refetch()} />
  }
  if (requests.data && !requests.data.count) {
    return (
      <EmptyState
        icon={SendIcon}
        title="No requests sent"
        description="On a public document you can view, use “Request edit access” to ask its owners."
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
              <TableHead>Status</TableHead>
              <TableHead className={SECONDARY_COLUMN}>Requested</TableHead>
              <TableHead className={SECONDARY_COLUMN}>Answered by</TableHead>
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
                    <TableCell>
                      <AccessRequestStatusBadge status={accessRequest.status} />
                    </TableCell>
                    <TableCell className={cn(SECONDARY_COLUMN, 'text-muted-foreground')}>
                      {formatDate(accessRequest.created)}
                    </TableCell>
                    <TableCell className={cn(SECONDARY_COLUMN, 'text-muted-foreground')}>
                      {accessRequest.reviewed_by_email
                        ? displayName({
                            name: accessRequest.reviewed_by_name,
                            email: accessRequest.reviewed_by_email,
                          })
                        : '—'}
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
