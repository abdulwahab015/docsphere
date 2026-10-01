import { zodResolver } from '@hookform/resolvers/zod'
import { PencilIcon } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'

import type { Project } from '@/api/types'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { ProjectDetailsFields } from '@/features/projects/components/ProjectDetailsFields'
import { useUpdateProject } from '@/features/projects/hooks'
import { projectFormSchema, type ProjectFormValues } from '@/features/projects/schemas'
import { applyApiErrors } from '@/lib/form-errors'

function formValues(project: Project): ProjectFormValues {
  return {
    name: project.name,
    description: project.description ?? '',
    visibility: project.visibility,
  }
}

export function EditProjectDialog({ project }: { project: Project }) {
  const [open, setOpen] = useState(false)
  const updateProject = useUpdateProject(project.id)
  const form = useForm<ProjectFormValues>({
    resolver: zodResolver(projectFormSchema),
    values: formValues(project),
  })

  const onSubmit = form.handleSubmit(({ name, description }) =>
    updateProject.mutate(
      { name, description: description || null },
      {
        onSuccess: () => {
          toast.success('Project updated.')
          setOpen(false)
        },
        onError: (error) => applyApiErrors(error, form),
      },
    ),
  )

  const onOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (!nextOpen) {
      form.reset(formValues(project))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <PencilIcon aria-hidden />
          Edit
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Edit project</DialogTitle>
          </DialogHeader>
          <FormAlert message={form.formState.errors.root?.server?.message} />
          <ProjectDetailsFields form={form} />
          <DialogFooter>
            <SubmitButton isPending={updateProject.isPending} disabled={!form.formState.isDirty}>
              Save changes
            </SubmitButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
