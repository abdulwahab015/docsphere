import { z } from 'zod'

export const ORGANIZATION_NAME_MAX_LENGTH = 100

export const organizationNameSchema = z
  .string()
  .trim()
  .min(1, { error: 'Enter your organization name.' })
  .max(ORGANIZATION_NAME_MAX_LENGTH, {
    error: `Use at most ${ORGANIZATION_NAME_MAX_LENGTH} characters.`,
  })

export const organizationSettingsSchema = z.object({ name: organizationNameSchema })
