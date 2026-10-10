import type { FieldValues, Path, UseFormReturn } from 'react-hook-form'

import { parseApiError } from '@/api/errors'

export const SERVER_ERROR_FIELD = 'root.server'

/**
 * Shows an API error on a react-hook-form form: messages for fields the form
 * has go under those fields; everything else (`detail`, `non_field_errors`,
 * or an error on a field the form doesn't render) becomes one form-level
 * message.
 */
export function applyApiErrors<TValues extends FieldValues>(
  error: unknown,
  form: UseFormReturn<TValues>,
) {
  const { formMessage, fieldErrors } = parseApiError(error)
  const formFields = new Set(Object.keys(form.getValues()))
  const formLevelMessages = formMessage ? [formMessage] : []

  for (const [field, message] of Object.entries(fieldErrors)) {
    if (formFields.has(field)) {
      form.setError(field as Path<TValues>, { type: 'server', message })
    } else {
      formLevelMessages.push(message)
    }
  }

  if (formLevelMessages.length) {
    form.setError(SERVER_ERROR_FIELD, { type: 'server', message: formLevelMessages.join(' ') })
  }
}
