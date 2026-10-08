import { apiClient } from '@/api/client'
import type {
  CurrentUser,
  CurrentUserUpdatePayload,
  PasswordChangePayload,
  TokenPair,
} from '@/api/types'

export async function changePassword(payload: PasswordChangePayload) {
  const { data } = await apiClient.post<TokenPair>('/users/me/password/', payload)
  return data
}

export async function updateCurrentUser(payload: CurrentUserUpdatePayload) {
  const { data } = await apiClient.patch<CurrentUser>('/users/me/', payload)
  return data
}
