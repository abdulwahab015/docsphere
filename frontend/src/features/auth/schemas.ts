import { z } from 'zod'

// Mirrors the backend's password policy so most mistakes are caught before a
// round trip. The server stays authoritative: it also rejects common passwords
// and ones too similar to the email address.
export const MIN_PASSWORD_LENGTH = 8
export const MAX_PASSWORD_LENGTH = 128
const ORGANIZATION_NAME_MAX_LENGTH = 100
const SPECIAL_CHARACTER = /[!@#$%^&*()_+\-=[\]{};:'"\\|,.<>/?~`]/

const PASSWORDS_DIFFER = { error: 'Passwords do not match.', path: ['confirm_password'] }

const emailSchema = z.email({ error: 'Enter a valid email address.' })

export const passwordSchema = z
  .string()
  .min(MIN_PASSWORD_LENGTH, { error: `Use at least ${MIN_PASSWORD_LENGTH} characters.` })
  .max(MAX_PASSWORD_LENGTH, { error: `Use at most ${MAX_PASSWORD_LENGTH} characters.` })
  .regex(/\p{Ll}/u, { error: 'Include a lowercase letter.' })
  .regex(/\p{Lu}/u, { error: 'Include an uppercase letter.' })
  .regex(/\p{Nd}/u, { error: 'Include a digit.' })
  .regex(SPECIAL_CHARACTER, { error: 'Include a special character.' })

export const PASSWORD_HINT = `At least ${MIN_PASSWORD_LENGTH} characters, with upper and lowercase letters, a digit and a special character.`

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, { error: 'Enter your password.' }),
})

export const signupSchema = z
  .object({
    name: z
      .string()
      .trim()
      .min(1, { error: 'Enter your organization name.' })
      .max(ORGANIZATION_NAME_MAX_LENGTH, {
        error: `Use at most ${ORGANIZATION_NAME_MAX_LENGTH} characters.`,
      }),
    billing_email: z.union([z.literal(''), emailSchema]),
    admin_email: emailSchema,
    admin_password: passwordSchema,
    confirm_password: z.string(),
  })
  .refine((values) => values.admin_password === values.confirm_password, PASSWORDS_DIFFER)

export const forgotPasswordSchema = z.object({
  email: emailSchema,
})

export const resetPasswordSchema = z
  .object({
    new_password: passwordSchema,
    confirm_password: z.string(),
  })
  .refine((values) => values.new_password === values.confirm_password, PASSWORDS_DIFFER)

export const acceptInvitationSchema = z
  .object({
    password: passwordSchema,
    confirm_password: z.string(),
  })
  .refine((values) => values.password === values.confirm_password, PASSWORDS_DIFFER)
