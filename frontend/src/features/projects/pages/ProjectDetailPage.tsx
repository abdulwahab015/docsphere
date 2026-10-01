import { ArrowLeftIcon } from 'lucide-react'
import { Link } from 'react-router'

import { PATHS } from '@/app/paths'
import type { Project } from '@/api/types'
import { AccessLevelBadge } from '@/components/AccessBadges'
import { ErrorState, NotFoundState } from '@/components/ErrorState'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { DeleteProjectButton } from '@/features/projects/components/DeleteProjectButton'
import { EditProjectDialog } from '@/features/projects/components/EditProjectDialog'
import { ProjectVisibilityCard } from '@/features/projects/components/ProjectVisibilityCard'
import { useProject } from '@/features/projects/hooks'
import { useIdParam } from '@/hooks/use-id-param'
import { can } from '@/lib/access'
import { formatDate } from '@/lib/format'

function BackToProjects() {
  return (
    <Button asChild variant="ghost" size="sm" className="self-start">
      <Link to={PATHS.projects}>
        <ArrowLeftIcon aria-hidden />
        Projects
      </Link>
    </Button>
  )
}

export function ProjectDetailPage() {
  const projectId = useIdParam('projectId')

  return (
    <>
      <BackToProjects />
      {projectId ? <ProjectDetail projectId={projectId} /> : <NotFoundState />}
    </>
  )
}

function ProjectDetail({ projectId }: { projectId: number }) {
  const project = useProject(projectId)

  if (project.isError) {
    return <ErrorState error={project.error} onRetry={() => void project.refetch()} />
  }
  if (!project.data) {
    return <Skeleton className="h-48 w-full" aria-label="Loading project" />
  }
  return <ProjectOverview project={project.data} />
}

function ProjectOverview({ project }: { project: Project }) {
  return (
    <>
      <PageHeader
        title={project.name}
        description={project.description || 'No description.'}
        actions={
          <>
            {can(project.access_level, 'WRITE') && <EditProjectDialog project={project} />}
            {can(project.access_level, 'DELETE') && <DeleteProjectButton project={project} />}
          </>
        }
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <ProjectVisibilityCard project={project} />
        <Card>
          <CardHeader>
            <CardTitle>
              <h2>Details</h2>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
              <dt className="text-muted-foreground">Your access</dt>
              <dd>
                <AccessLevelBadge level={project.access_level} />
              </dd>
              <dt className="text-muted-foreground">Created by</dt>
              <dd>{project.created_by_email}</dd>
              <dt className="text-muted-foreground">Created</dt>
              <dd>{formatDate(project.created)}</dd>
              <dt className="text-muted-foreground">Updated</dt>
              <dd>{formatDate(project.modified)}</dd>
            </dl>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
