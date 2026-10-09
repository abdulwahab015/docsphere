import { z } from 'zod'

// The length of the codes authenticator apps show.
export const APP_CODE_DIGITS = 6

export const appCodeSchema = z.object({
  otp: z
    .string()
    .trim()
    .regex(new RegExp(`^\\d{${APP_CODE_DIGITS}}$`), {
      error: `Enter the ${APP_CODE_DIGITS}-digit code from your app.`,
    }),
})

export const currentPasswordSchema = z.object({
  current_password: z.string().min(1, { error: 'Enter your current password.' }),
})
