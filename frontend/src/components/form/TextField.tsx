import { type ComponentProps, useId } from 'react'

import { Field, FieldDescription, FieldError, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'

interface TextFieldProps extends ComponentProps<typeof Input> {
  name: string
  label: string
  description?: string
  error?: string
}

export function TextField({ name, label, description, error, id, ...inputProps }: TextFieldProps) {
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
      <Input
        id={inputId}
        name={name}
        aria-invalid={Boolean(error) || undefined}
        aria-describedby={describedBy || undefined}
        {...inputProps}
      />
      {description && <FieldDescription id={descriptionId}>{description}</FieldDescription>}
      {error && <FieldError id={errorId}>{error}</FieldError>}
    </Field>
  )
}
