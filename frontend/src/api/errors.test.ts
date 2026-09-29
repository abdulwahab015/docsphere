import { http, HttpResponse, type JsonBodyType } from 'msw'

import { apiClient } from '@/api/client'
import {
  getErrorStatus,
  NETWORK_ERROR_MESSAGE,
  parseApiError,
  SERVER_ERROR_MESSAGE,
  UNEXPECTED_ERROR_MESSAGE,
} from '@/api/errors'
import { apiUrl, server } from '@/test/server'

const PROBE_PATH = '/probe/'

/** The error a real request gets back when the API answers with `response`. */
async function errorFrom(response: Response) {
  server.use(http.get(apiUrl(PROBE_PATH), () => response))
  try {
    await apiClient.get(PROBE_PATH)
  } catch (error) {
    return error
  }
  throw new Error('Expected the request to fail.')
}

function failWith(status: number, body: JsonBodyType) {
  return errorFrom(HttpResponse.json(body, { status }))
}

describe('parseApiError', () => {
  it('maps field errors onto their fields', async () => {
    const error = await failWith(400, {
      admin_email: ['A user with this email already exists.'],
      name: ['This field is required.', 'Too short.'],
    })

    expect(parseApiError(error)).toEqual({
      status: 400,
      formMessage: undefined,
      fieldErrors: {
        admin_email: 'A user with this email already exists.',
        name: 'This field is required. Too short.',
      },
    })
  })

  it('uses detail as the form-level message and ignores code', async () => {
    const error = await failWith(401, {
      detail: 'No active account found with the given credentials',
      code: 'no_active_account',
    })

    expect(parseApiError(error)).toEqual({
      status: 401,
      formMessage: 'No active account found with the given credentials',
      fieldErrors: {},
    })
  })

  it('treats non_field_errors as a form-level message', async () => {
    const error = await failWith(400, { non_field_errors: ['Invalid or expired reset link.'] })

    expect(parseApiError(error).formMessage).toBe('Invalid or expired reset link.')
  })

  it('treats a bare list of messages as a form-level message', async () => {
    const error = await failWith(400, ['This invitation is no longer pending.'])

    expect(parseApiError(error).formMessage).toBe('This invitation is no longer pending.')
  })

  it('falls back to a generic message for a body it cannot read', async () => {
    const error = await failWith(400, { detail: 42 })

    expect(parseApiError(error).formMessage).toBe(UNEXPECTED_ERROR_MESSAGE)
  })

  it('hides server error details behind a generic message', async () => {
    const error = await failWith(500, { detail: 'Traceback (most recent call last)' })

    expect(parseApiError(error)).toMatchObject({ status: 500, formMessage: SERVER_ERROR_MESSAGE })
  })

  it('reports an unreachable server as a connection problem', async () => {
    const error = await errorFrom(HttpResponse.error())

    expect(parseApiError(error)).toMatchObject({
      status: undefined,
      formMessage: NETWORK_ERROR_MESSAGE,
    })
  })

  it('handles errors that did not come from the API', () => {
    expect(parseApiError(new TypeError('boom'))).toEqual({
      status: undefined,
      formMessage: UNEXPECTED_ERROR_MESSAGE,
      fieldErrors: {},
    })
  })
})

describe('getErrorStatus', () => {
  it("returns the response's status", async () => {
    expect(getErrorStatus(await failWith(402, {}))).toBe(402)
  })

  it('returns undefined for errors without a response', () => {
    expect(getErrorStatus(new Error('boom'))).toBeUndefined()
  })
})
