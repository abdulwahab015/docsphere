import { ArchiveRestoreIcon, ArrowLeftIcon, Trash2Icon } from 'lucide-react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { PATHS } from '@/app/paths'
import type { Project } from '@/api/types'
import { AccessLevelBadge, VisibilityBadge } from '@/components/AccessBadges'
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
import { useProjectTrash, useRestoreProject } from '@/features/projects/hooks'
import { useListParams } from '@/hooks/use-list-params'
import { formatDate } from '@/lib/format'
import { SECONDARY_COLUMN } from '@/lib/table-columns'
import { cn } from '@/lib/utils'

export function ProjectTrashPage() {
  const { page, setPage } = useListParams()
  const trash = useProjectTrash(page)
  const restore = useRestoreProject()

  const restoreProject = (project: Project) =>
    restore.mutate(project.id, {
      onSuccess: () => toast.success(`Restored "${project.name}".`),
      onError: () => toast.error(`Couldn't restore "${project.name}".`),
    })

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="self-start">
        <Link to={PATHS.projects}>
          <ArrowLeftIcon aria-hidden />
          Projects
        </Link>
      </Button>
      <PageHeader
        title="Project trash"
        description="Deleted projects stay here until an admin restores them, along with their documents. Their names stay reserved meanwhile."
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
                  <TableHead>Name</TableHead>
                  <TableHead className={SECONDARY_COLUMN}>Visibility</TableHead>
                  <TableHead>Your access</TableHead>
                  <TableHead className={SECONDARY_COLUMN}>Deleted</TableHead>
                  <TableHead>
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trash.data.results.map((project) => (
                  <TableRow key={project.id}>
                    <TableCell className="font-medium">{project.name}</TableCell>
                    <TableCell className={SECONDARY_COLUMN}>
                      <VisibilityBadge visibility={project.visibility} />
                    </TableCell>
                    <TableCell>
                      <AccessLevelBadge level={project.access_level} />
                    </TableCell>
                    <TableCell className={cn(SECONDARY_COLUMN, 'text-muted-foreground')}>
                      {formatDate(project.modified)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={restore.isPending && restore.variables === project.id}
                        onClick={() => restoreProject(project)}
                        aria-label={`Restore ${project.name}`}
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
