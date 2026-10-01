import { z } from 'zod'

import { emailSchema } from '@/lib/schemas'

export const invitationSchema = z.object({ email: emailSchema })

export type InvitationValues = z.infer<typeof invitationSchema>
