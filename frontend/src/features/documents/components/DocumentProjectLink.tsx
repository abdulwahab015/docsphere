import { Link } from 'react-router'

import { projectPath } from '@/app/paths'
import { Skeleton } from '@/components/ui/skeleton'
import { useProject } from '@/features/projects/hooks'

/** Names the project a document is filed under - but only when the reader
 * can access that project too. Access to a document says nothing about its
 * project, and a private project the reader can't see must stay unnamed. */
export function DocumentProjectLink({ projectId }: { projectId: number }) {
  const project = useProject(projectId)

  if (project.data) {
    return (
      <Link to={projectPath(projectId)} className="hover:underline">
        {project.data.name}
      </Link>
    )
  }
  if (project.isError) {
    return <span className="text-muted-foreground">A project you can&apos;t open</span>
  }
  return <Skeleton className="h-4 w-24" aria-label="Loading project" />
}
