import { useState } from 'react'
import { toast } from 'sonner'

import type { Project } from '@/api/types'
import { VisibilityBadge } from '@/components/AccessBadges'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useSignedInMember } from '@/features/auth/hooks'
import { useUpdateProject } from '@/features/projects/hooks'
import { projectVisibilityDescriptions } from '@/features/projects/visibility'
import { can } from '@/lib/access'

export function ProjectVisibilityCard({ project }: { project: Project }) {
  const user = useSignedInMember()
  const [confirming, setConfirming] = useState(false)
  const updateProject = useUpdateProject(project.id)
  const descriptions = projectVisibilityDescriptions(user.organization.name)
  const isPublic = project.visibility === 'PUBLIC'

  const changeVisibility = () =>
    updateProject.mutate(
      { visibility: isPublic ? 'PRIVATE' : 'PUBLIC' },
      {
        onSuccess: (updated) => {
          toast.success(
            updated.visibility === 'PUBLIC' ? 'Project is now public.' : 'Project is now private.',
          )
          setConfirming(false)
        },
        onError: () => {
          toast.error("Couldn't change the project's visibility.")
          setConfirming(false)
        },
      },
    )

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Visibility</h2>
        </CardTitle>
        <CardDescription>{descriptions[project.visibility]}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center justify-between gap-3">
        <VisibilityBadge visibility={project.visibility} />
        {/* Changing visibility is Owner-only, the same bar as sharing. */}
        {can(project.access_level, 'RESHARE') && (
          <ConfirmDialog
            open={confirming}
            onOpenChange={setConfirming}
            trigger={<Button variant="outline">{isPublic ? 'Make private' : 'Make public'}</Button>}
            title={isPublic ? 'Make this project private?' : 'Make this project public?'}
            description={
              isPublic
                ? 'Members without a permission of their own will lose access.'
                : descriptions.PUBLIC
            }
            confirmLabel={isPublic ? 'Make private' : 'Make public'}
            onConfirm={changeVisibility}
            isPending={updateProject.isPending}
          />
        )}
      </CardContent>
    </Card>
  )
}
