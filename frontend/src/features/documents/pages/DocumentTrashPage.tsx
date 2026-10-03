import { ArchiveRestoreIcon, ArrowLeftIcon, Trash2Icon } from 'lucide-react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { PATHS } from '@/app/paths'
import { actionErrorMessage } from '@/api/errors'
import type { Document } from '@/api/types'
import { VisibilityBadge } from '@/components/AccessBadges'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { PageHeader } from '@/components/PageHeader'
import { Pagination } from '@/components/Pagination'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useDocumentTrash, useRestoreDocument } from '@/features/documents/hooks'
import { useListParams } from '@/hooks/use-list-params'
import { formatDate } from '@/lib/format'
import { SECONDARY_COLUMN } from '@/lib/table-columns'

export function DocumentTrashPage() {
  const { page, setPage } = useListParams()
  const trash = useDocumentTrash(page)
  const restore = useRestoreDocument()

  const restoreDocument = (document: Document) =>
    restore.mutate(document.id, {
      onSuccess: () => toast.success(`Restored "${document.title}".`),
      // e.g. the document's project is in the trash and must be restored first.
      onError: (error) =>
        toast.error(actionErrorMessage(error, `Couldn't restore "${document.title}".`)),
    })

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="self-start">
        <Link to={PATHS.documents}>
          <ArrowLeftIcon aria-hidden />
          Documents
        </Link>
      </Button>
      <PageHeader
        title="Document trash"
        description="Documents you own that were deleted. Restoring one brings it back for everyone who had access."
      />
      {trash.isError ? (
        <ErrorState error={trash.error} onRetry={() => void trash.refetch()} />
      ) : !trash.data ? (
        <Skeleton className="h-32 w-full" aria-label="Loading trash" />
      ) : !trash.data.count ? (
        <EmptyState icon={Trash2Icon} title="The trash is empty" />
      ) : (
        <>
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead className={SECONDARY_COLUMN}>Visibility</TableHead>
                  <TableHead>Deleted</TableHead>
                  <TableHead>
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trash.data.results.map((document) => (
                  <TableRow key={document.id}>
                    <TableCell className="font-medium">{document.title}</TableCell>
                    <TableCell className={SECONDARY_COLUMN}>
                      <VisibilityBadge visibility={document.visibility} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(document.modified)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={restore.isPending && restore.variables === document.id}
                        onClick={() => restoreDocument(document)}
                        aria-label={`Restore ${document.title}`}
                      >
                        <ArchiveRestoreIcon aria-hidden />
                        Restore
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pagination page={page} count={trash.data.count} onPageChange={setPage} />
        </>
      )}
    </>
  )
}
