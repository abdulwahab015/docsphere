import { FolderIcon, Trash2Icon } from 'lucide-react'
import { Link } from 'react-router'

import { PATHS, projectPath } from '@/app/paths'
import { AccessLevelBadge, VisibilityBadge } from '@/components/AccessBadges'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { PageHeader } from '@/components/PageHeader'
import { Pagination } from '@/components/Pagination'
import { SearchInput } from '@/components/SearchInput'
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
import { useSignedInMember } from '@/features/auth/hooks'
import { CreateProjectDialog } from '@/features/projects/components/CreateProjectDialog'
import { useProjects } from '@/features/projects/hooks'
import { useListParams } from '@/hooks/use-list-params'
import { formatDate } from '@/lib/format'
import { creatorName } from '@/lib/people'
import { SECONDARY_COLUMN } from '@/lib/table-columns'
import { cn } from '@/lib/utils'

const LOADING_ROWS = 5

export function ProjectsPage() {
  const user = useSignedInMember()
  const isAdmin = user.org_role === 'ADMIN'
  const { page, search, setPage, setSearch } = useListParams()
  const projects = useProjects({ page, search })

  return (
    <>
      <PageHeader
        title="Projects"
        description="Projects you have access to, including every public one."
        actions={
          // Creating and restoring projects are admin-only in the API.
          isAdmin && (
            <>
              <Button asChild variant="outline">
                <Link to={PATHS.projectTrash}>
                  <Trash2Icon aria-hidden />
                  Trash
                </Link>
              </Button>
              <CreateProjectDialog />
            </>
          )
        }
      />
      <SearchInput
        value={search}
        onSearch={setSearch}
        label="Search projects"
        placeholder="Search by name"
      />
      {projects.isError ? (
        <ErrorState error={projects.error} onRetry={() => void projects.refetch()} />
      ) : projects.data && !projects.data.count ? (
        <EmptyState
          icon={FolderIcon}
          title={search ? 'No matches' : 'No projects yet'}
          description={
            search
              ? `No project's name matches "${search}".`
              : isAdmin
                ? 'Create the first one to start organizing documents.'
                : 'Projects show up here once someone shares one with you or makes one public.'
          }
        />
      ) : (
        <>
          <div className="rounded-lg border">
            <Table aria-busy={projects.isFetching}>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Visibility</TableHead>
                  <TableHead>Your access</TableHead>
                  <TableHead className={SECONDARY_COLUMN}>Created by</TableHead>
                  <TableHead className={SECONDARY_COLUMN}>Updated</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {projects.data
                  ? projects.data.results.map((project) => (
                      <TableRow key={project.id}>
                        <TableCell className="font-medium">
                          <Link to={projectPath(project.id)} className="hover:underline">
                            {project.name}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <VisibilityBadge visibility={project.visibility} />
                        </TableCell>
                        <TableCell>
                          <AccessLevelBadge level={project.access_level} />
                        </TableCell>
                        <TableCell className={cn(SECONDARY_COLUMN, 'text-muted-foreground')}>
                          {creatorName(project)}
                        </TableCell>
                        <TableCell className={cn(SECONDARY_COLUMN, 'text-muted-foreground')}>
                          {formatDate(project.modified)}
                        </TableCell>
                      </TableRow>
                    ))
                  : Array.from({ length: LOADING_ROWS }, (_unused, index) => (
                      <TableRow key={index}>
                        <TableCell colSpan={5}>
                          <Skeleton className="h-5 w-full" />
                        </TableCell>
                      </TableRow>
                    ))}
              </TableBody>
            </Table>
          </div>
          {projects.data && (
            <Pagination page={page} count={projects.data.count} onPageChange={setPage} />
          )}
        </>
      )}
    </>
  )
}
