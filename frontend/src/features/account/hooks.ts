import { useMutation } from '@tanstack/react-query'

import type { PasswordChangePayload } from '@/api/types'
import { changePassword } from '@/features/account/api'
import { renewSession } from '@/features/auth/session'

/** Changes the signed-in user's password. The API revokes every session they
 * had and returns a fresh token pair, which keeps this one going. */
export function useChangePassword() {
  return useMutation({
    mutationFn: async (payload: PasswordChangePayload) =>
      renewSession(await changePassword(payload)),
  })
}
