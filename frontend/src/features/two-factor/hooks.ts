import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { authKeys } from '@/features/auth/query-keys'
import {
  confirmTwoFactor,
  fetchTwoFactorStatus,
  makeNewRecoveryCodes,
  startTwoFactorSetup,
  turnOffTwoFactor,
} from '@/features/two-factor/api'
import { twoFactorKeys } from '@/features/two-factor/query-keys'

export function useTwoFactorStatus() {
  return useQuery({ queryKey: twoFactorKeys.status, queryFn: fetchTwoFactorStatus })
}

/** Re-reads whether two-factor sign-in is on: the session's user (what lets
 * someone past their organization's requirement) and the account page's
 * status. Turning it on or off doesn't do this itself, since what's re-read
 * replaces the screen that did it: run it once setup is finished (the
 * recovery codes are shown only once), and once a dialog has finished closing
 * (so it isn't removed halfway through). */
export function useRereadTwoFactor() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: authKeys.currentUser })
    void queryClient.invalidateQueries({ queryKey: twoFactorKeys.status })
  }
}

export function useStartTwoFactorSetup() {
  return useMutation({ mutationFn: startTwoFactorSetup })
}

/** Marks the status stale whenever two-factor sign-in or its codes change. */
function useTwoFactorMutation<TVariables, TData>(
  mutationFn: (variables: TVariables) => Promise<TData>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: twoFactorKeys.status }),
  })
}

/** Leaves the status alone: see `useRereadTwoFactor`. */
export function useConfirmTwoFactor() {
  return useMutation({ mutationFn: confirmTwoFactor })
}

/** Leaves the status alone: see `useRereadTwoFactor`. */
export function useTurnOffTwoFactor() {
  return useMutation({ mutationFn: turnOffTwoFactor })
}

export function useMakeNewRecoveryCodes() {
  return useTwoFactorMutation(makeNewRecoveryCodes)
}
