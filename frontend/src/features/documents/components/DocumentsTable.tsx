import { Link } from 'react-router'

import { documentPath } from '@/app/paths'
import type { Document, Paginated } from '@/api/types'
import { AccessLevelBadge, VisibilityBadge } from '@/components/AccessBadges'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatDate } from '@/lib/format'
import { creatorName } from '@/lib/people'
import { SECONDARY_COLUMN } from '@/lib/table-columns'
import { cn } from '@/lib/utils'

const LOADING_ROWS = 5
const COLUMN_COUNT = 5

interface DocumentsTableProps {
  documents: Paginated<Document> | undefined
  isFetching: boolean
  /** Mark documents that aren't filed under any project. */
  markPersonal?: boolean
}

export function DocumentsTable({
  documents,
  isFetching,
  markPersonal = false,
}: DocumentsTableProps) {
  return (
    <div className="rounded-lg border">
      <Table aria-busy={isFetching}>
        <TableHeader>
          <TableRow>
            <TableHead>Title</TableHead>
            <TableHead>Visibility</TableHead>
            <TableHead>Your access</TableHead>
            <TableHead className={SECONDARY_COLUMN}>Created by</TableHead>
            <TableHead className={SECONDARY_COLUMN}>Updated</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents
            ? documents.results.map((document) => (
                <TableRow key={document.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <Link to={documentPath(document.id)} className="hover:underline">
                        {document.title}
                      </Link>
                      {markPersonal && !document.project && (
                        <Badge variant="secondary">Personal</Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <VisibilityBadge visibility={document.visibility} />
                  </TableCell>
                  <TableCell>
                    <AccessLevelBadge level={document.access_level} />
                  </TableCell>
                  <TableCell className={cn(SECONDARY_COLUMN, 'text-muted-foreground')}>
                    {creatorName(document)}
                  </TableCell>
                  <TableCell className={cn(SECONDARY_COLUMN, 'text-muted-foreground')}>
                    {formatDate(document.modified)}
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
  )
}
