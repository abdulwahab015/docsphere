import { zodResolver } from '@hookform/resolvers/zod'
import { PlusIcon } from 'lucide-react'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { documentPath } from '@/app/paths'
import type { Project } from '@/api/types'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
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
import { useCreateDocument } from '@/features/documents/hooks'
import { newDocumentSchema, type NewDocumentValues } from '@/features/documents/schemas'
import { visibilityDescriptions } from '@/lib/access'
import { applyApiErrors } from '@/lib/form-errors'

const EMPTY_DOCUMENT: NewDocumentValues = { title: '', visibility: 'PRIVATE' }

/** Creates a document in `project`, or a personal one when there's none. */
export function CreateDocumentDialog({ project }: { project?: Project }) {
  const user = useSignedInMember()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const createDocument = useCreateDocument()
  const form = useForm<NewDocumentValues>({
    resolver: zodResolver(newDocumentSchema),
    defaultValues: EMPTY_DOCUMENT,
  })

  const onSubmit = form.handleSubmit(({ title, visibility }) =>
    createDocument.mutate(
      { title, content: '', visibility, project: project?.id ?? null },
      {
        onSuccess: (document) => {
          toast.success(`Created "${document.title}".`)
          setOpen(false)
          void navigate(documentPath(document.id))
        },
        onError: (error) => applyApiErrors(error, form),
      },
    ),
  )

  const onOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (!nextOpen) {
      form.reset(EMPTY_DOCUMENT)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <PlusIcon aria-hidden />
          New document
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>New document</DialogTitle>
            <DialogDescription>
              {project
                ? `In ${project.name}. You'll be the document's owner; access to the project doesn't include it.`
                : "A personal document, not filed under any project. You'll be its owner."}
            </DialogDescription>
          </DialogHeader>
          <FormAlert message={form.formState.errors.root?.server?.message} />
          <TextField
            label="Title"
            autoComplete="off"
            error={form.formState.errors.title?.message}
            {...form.register('title')}
          />
          <Controller
            control={form.control}
            name="visibility"
            render={({ field }) => (
              <VisibilityField
                value={field.value}
                onChange={field.onChange}
                descriptions={visibilityDescriptions(user.organization.name)}
              />
            )}
          />
          <DialogFooter>
            <SubmitButton isPending={createDocument.isPending}>Create document</SubmitButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
