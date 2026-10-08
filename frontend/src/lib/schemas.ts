import { z } from 'zod'

export const emailSchema = z.email({ error: 'Enter a valid email address.' })

/** An optional email input: blank means "none", sent to the API as `null`. */
export const optionalEmailSchema = z.union([z.literal(''), emailSchema])

// The API's limit on a person's name (users.constants.MAX_NAME_LENGTH).
export const MAX_NAME_LENGTH = 150

/** A person's name, as they'd like to be shown. Optional: blank means no name
 * yet, and their email address stands in for it. */
export const nameSchema = z
  .string()
  .trim()
  .max(MAX_NAME_LENGTH, { error: `Use at most ${MAX_NAME_LENGTH} characters.` })
