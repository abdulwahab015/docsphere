import type { UseFormReturn } from 'react-hook-form'

import { TextareaField } from '@/components/form/TextareaField'
import { TextField } from '@/components/form/TextField'
import type { ProjectFormValues } from '@/features/projects/schemas'

/** The name and description inputs shared by the create and edit dialogs. */
export function ProjectDetailsFields({ form }: { form: UseFormReturn<ProjectFormValues> }) {
  const { errors } = form.formState

  return (
    <>
      <TextField
        label="Name"
        autoComplete="off"
        error={errors.name?.message}
        {...form.register('name')}
      />
      <TextareaField
        label="Description (optional)"
        rows={3}
        error={errors.description?.message}
        {...form.register('description')}
      />
    </>
  )
}
