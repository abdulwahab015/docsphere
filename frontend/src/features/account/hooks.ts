import { useMutation, useQueryClient } from '@tanstack/react-query'

import type { CurrentUserUpdatePayload, PasswordChangePayload } from '@/api/types'
import {
  changePassword,
  deleteAccount,
  requestEmailChange,
  updateCurrentUser,
} from '@/features/account/api'
import { authKeys } from '@/features/auth/query-keys'
import { endSessionDeliberately, renewSession } from '@/features/auth/session'
import { announceSessionChange } from '@/features/auth/session-broadcast'

/** Changes the signed-in user's password. The API revokes every session they
 * had and returns a fresh token pair, which keeps this one going. */
export function useChangePassword() {
  return useMutation({
    mutationFn: async (payload: PasswordChangePayload) =>
      renewSession(await changePassword(payload)),
  })
}

/** Changes the signed-in user's name. The response is the whole current user,
 * so the session is updated in place and every screen shows the new name. */
export function useUpdateName() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CurrentUserUpdatePayload) => updateCurrentUser(payload),
    onSuccess: (user) => queryClient.setQueryData(authKeys.currentUser, user),
  })
}

/** Emails a confirmation link to the new address. Nothing changes until it's
 * followed, so the session and its data stay as they are. */
export function useRequestEmailChange() {
  return useMutation({ mutationFn: requestEmailChange })
}

/** Deletes the signed-in user's own account. The API has signed them out
 * everywhere, so this tab ends its session as a deliberate logout would, and
 * other tabs re-read theirs. */
export function useDeleteAccount() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteAccount,
    onSuccess: () => {
      endSessionDeliberately(queryClient)
      announceSessionChange()
    },
  })
}
