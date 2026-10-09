import { isAxiosError } from 'axios'

import { HTTP_STATUS } from '@/api/constants'

export const NETWORK_ERROR_MESSAGE = "Can't reach the server. Check your connection and try again."
export const SERVER_ERROR_MESSAGE = 'Something went wrong on our side. Please try again.'
export const UNEXPECTED_ERROR_MESSAGE = 'Something went wrong. Please try again.'

// Keys DRF puts on an error body that don't name an input field.
const FORM_LEVEL_KEYS = new Set(['detail', 'non_field_errors'])
const IGNORED_KEYS = new Set(['code'])

export interface ParsedApiError {
  status: number | undefined
  formMessage: string | undefined
  fieldErrors: Record<string, string>
}

export function getErrorStatus(error: unknown) {
  return isAxiosError(error) ? error.response?.status : undefined
}

/** The stable `code` the API puts beside `detail` on some refusals, telling
 * apart two answers with the same status (e.g. `email_unverified`). */
export function getErrorCode(error: unknown) {
  const body: unknown = isAxiosError(error) ? error.response?.data : undefined
  if (body && typeof body === 'object' && 'code' in body && typeof body.code === 'string') {
    return body.code
  }
  return undefined
}

function toMessage(value: unknown) {
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value)) {
    return value.filter((item) => typeof item === 'string').join(' ')
  }
  return ''
}

/**
 * Normalizes any error from an API call into one form-level message plus
 * per-field messages, following DRF's error shapes: `{"detail": "..."}`,
 * `{"field": ["..."]}`, `{"non_field_errors": ["..."]}` and a bare `["..."]`.
 */
export function parseApiError(error: unknown): ParsedApiError {
  const status = getErrorStatus(error)
  const parsed: ParsedApiError = { status, formMessage: undefined, fieldErrors: {} }

  if (!isAxiosError(error)) {
    return { ...parsed, formMessage: UNEXPECTED_ERROR_MESSAGE }
  }
  if (!error.response) {
    return { ...parsed, formMessage: NETWORK_ERROR_MESSAGE }
  }
  if (status && status >= HTTP_STATUS.serverError) {
    return { ...parsed, formMessage: SERVER_ERROR_MESSAGE }
  }

  const body: unknown = error.response.data
  const formMessages: string[] = []

  if (Array.isArray(body)) {
    // A view-level `ValidationError("...")` arrives as a bare list of messages.
    formMessages.push(toMessage(body))
  } else if (body && typeof body === 'object') {
    for (const [key, value] of Object.entries(body)) {
      const message = toMessage(value)
      if (!message || IGNORED_KEYS.has(key)) {
        continue
      }
      if (FORM_LEVEL_KEYS.has(key)) {
        formMessages.push(message)
      } else {
        parsed.fieldErrors[key] = message
      }
    }
  }

  const hasFieldErrors = Object.keys(parsed.fieldErrors).length > 0
  const formMessage = formMessages.filter(Boolean).join(' ')
  if (formMessage) {
    parsed.formMessage = formMessage
  } else if (!hasFieldErrors) {
    parsed.formMessage = UNEXPECTED_ERROR_MESSAGE
  }
  return parsed
}

/**
 * One line to report a failed action (in a toast, say). A 400 carries the
 * API's reason, which is worth reading - e.g. "Cannot revoke the document's
 * last Owner." - so it's shown, whether it came as a form-level or a field
 * message. Anything else gets `fallback`.
 */
export function actionErrorMessage(error: unknown, fallback: string) {
  const { status, formMessage, fieldErrors } = parseApiError(error)
  if (status !== HTTP_STATUS.badRequest) {
    return fallback
  }
  // parseApiError leaves the form message unset only when there are field errors.
  return formMessage ?? Object.values(fieldErrors).join(' ')
}
