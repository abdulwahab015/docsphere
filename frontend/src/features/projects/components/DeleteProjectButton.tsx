import { Trash2Icon } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { PATHS } from '@/app/paths'
import type { Project } from '@/api/types'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Button } from '@/components/ui/button'
import { useDeleteProject } from '@/features/projects/hooks'

export function DeleteProjectButton({ project }: { project: Project }) {
  const navigate = useNavigate()
  const [confirming, setConfirming] = useState(false)
  const deleteProject = useDeleteProject(project.id)

  const moveToTrash = () =>
    deleteProject.mutate(undefined, {
      onSuccess: () => {
        toast.success(`Moved "${project.name}" to the trash.`)
        void navigate(PATHS.projects)
      },
      onError: () => {
        toast.error(`Couldn't delete "${project.name}".`)
        setConfirming(false)
      },
    })

  return (
    <ConfirmDialog
      open={confirming}
      onOpenChange={setConfirming}
      trigger={
        <Button variant="destructive">
          <Trash2Icon aria-hidden />
          Delete
        </Button>
      }
      title={`Delete "${project.name}"?`}
      description="It moves to the trash and disappears for everyone, along with every document filed under it. An organization admin can restore it, which brings its documents back too."
      confirmLabel="Delete project"
      onConfirm={moveToTrash}
      isPending={deleteProject.isPending}
      destructive
    />
  )
}
