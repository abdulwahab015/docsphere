import { z } from 'zod'

export const PROJECT_NAME_MAX_LENGTH = 100

/** One shape for both the create and edit dialogs; editing doesn't show or
 * send `visibility`, which has its own Owner-only control. */
export const projectFormSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, { error: 'Enter a project name.' })
    .max(PROJECT_NAME_MAX_LENGTH, { error: `Use at most ${PROJECT_NAME_MAX_LENGTH} characters.` }),
  description: z.string().trim(),
  visibility: z.enum(['PRIVATE', 'PUBLIC']),
})

export type ProjectFormValues = z.infer<typeof projectFormSchema>
