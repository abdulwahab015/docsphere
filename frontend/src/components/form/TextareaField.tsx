import { type ComponentProps, useId } from 'react'

import { Field, FieldDescription, FieldError, FieldLabel } from '@/components/ui/field'
import { Textarea } from '@/components/ui/textarea'

interface TextareaFieldProps extends ComponentProps<typeof Textarea> {
  name: string
  label: string
  description?: string
  error?: string
}

export function TextareaField({
  name,
  label,
  description,
  error,
  id,
  ...textareaProps
}: TextareaFieldProps) {
  // Unique on the page, so two forms there can ask for the same field
  // (e.g. the current password) without their labels mixing up.
  const generatedId = useId()
  const inputId = id || generatedId
  const descriptionId = `${inputId}-description`
  const errorId = `${inputId}-error`
  const describedBy = [description && descriptionId, error && errorId].filter(Boolean).join(' ')

  return (
    <Field data-invalid={Boolean(error) || undefined}>
      <FieldLabel htmlFor={inputId}>{label}</FieldLabel>
      <Textarea
        id={inputId}
        name={name}
        aria-invalid={Boolean(error) || undefined}
        aria-describedby={describedBy || undefined}
        {...textareaProps}
      />
      {description && <FieldDescription id={descriptionId}>{description}</FieldDescription>}
      {error && <FieldError id={errorId}>{error}</FieldError>}
    </Field>
  )
}
