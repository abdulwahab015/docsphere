import { z } from 'zod'

import { optionalEmailSchema } from '@/lib/schemas'

export const billingEmailSchema = z.object({ billing_email: optionalEmailSchema })
