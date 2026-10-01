import { zodResolver } from '@hookform/resolvers/zod'
import { PlusIcon } from 'lucide-react'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { projectPath } from '@/app/paths'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { VisibilityField } from '@/components/form/VisibilityField'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { useSignedInMember } from '@/features/auth/hooks'
import { ProjectDetailsFields } from '@/features/projects/components/ProjectDetailsFields'
import { useCreateProject } from '@/features/projects/hooks'
import { projectFormSchema, type ProjectFormValues } from '@/features/projects/schemas'
import { projectVisibilityDescriptions } from '@/features/projects/visibility'
import { applyApiErrors } from '@/lib/form-errors'

const EMPTY_PROJECT: ProjectFormValues = { name: '', description: '', visibility: 'PRIVATE' }

export function CreateProjectDialog() {
  const user = useSignedInMember()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const createProject = useCreateProject()
  const form = useForm<ProjectFormValues>({
    resolver: zodResolver(projectFormSchema),
    defaultValues: EMPTY_PROJECT,
  })

  const onSubmit = form.handleSubmit(({ name, description, visibility }) =>
    createProject.mutate(
      { name, description: description || null, visibility },
      {
        onSuccess: (project) => {
          toast.success(`Created "${project.name}".`)
          setOpen(false)
          void navigate(projectPath(project.id))
        },
        onError: (error) => applyApiErrors(error, form),
      },
    ),
  )

  const onOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (!nextOpen) {
      form.reset(EMPTY_PROJECT)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <PlusIcon aria-hidden />
          New project
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>New project</DialogTitle>
            <DialogDescription>You&apos;ll be its owner.</DialogDescription>
          </DialogHeader>
          <FormAlert message={form.formState.errors.root?.server?.message} />
          <ProjectDetailsFields form={form} />
          <Controller
            control={form.control}
            name="visibility"
            render={({ field }) => (
              <VisibilityField
                value={field.value}
                onChange={field.onChange}
                descriptions={projectVisibilityDescriptions(user.organization.name)}
              />
            )}
          />
          <DialogFooter>
            <SubmitButton isPending={createProject.isPending}>Create project</SubmitButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
