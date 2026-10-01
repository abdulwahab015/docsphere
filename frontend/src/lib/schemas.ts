import { z } from 'zod'

export const emailSchema = z.email({ error: 'Enter a valid email address.' })

/** An optional email input: blank means "none", sent to the API as `null`. */
export const optionalEmailSchema = z.union([z.literal(''), emailSchema])
