import { z } from 'zod'

export const DOCUMENT_TITLE_MAX_LENGTH = 100

const titleSchema = z
  .string()
  .trim()
  .min(1, { error: 'Enter a title.' })
  .max(DOCUMENT_TITLE_MAX_LENGTH, { error: `Use at most ${DOCUMENT_TITLE_MAX_LENGTH} characters.` })

export const newDocumentSchema = z.object({
  title: titleSchema,
  visibility: z.enum(['PRIVATE', 'PUBLIC']),
})

export type NewDocumentValues = z.infer<typeof newDocumentSchema>

export const documentContentSchema = z.object({
  title: titleSchema,
  content: z.string(),
})

export type DocumentContentValues = z.infer<typeof documentContentSchema>
