import { z } from 'zod'

import { PASSWORDS_DIFFER, passwordSchema } from '@/features/auth/schemas'
import { emailSchema, nameSchema } from '@/lib/schemas'

export const nameFormSchema = z.object({ name: nameSchema })

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, { error: 'Enter your current password.' }),
    new_password: passwordSchema,
    confirm_password: z.string(),
  })
  .refine((values) => values.new_password === values.confirm_password, PASSWORDS_DIFFER)

export const changeEmailSchema = z.object({
  new_email: emailSchema,
  current_password: z.string().min(1, { error: 'Enter your current password.' }),
})
