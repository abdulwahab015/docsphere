import { apiClient } from '@/api/client'
import type {
  AccountDeletionPayload,
  CurrentUser,
  CurrentUserUpdatePayload,
  EmailChangeRequestPayload,
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

export async function requestEmailChange(payload: EmailChangeRequestPayload) {
  await apiClient.post('/users/me/email/', payload)
}

export async function deleteAccount(payload: AccountDeletionPayload) {
  await apiClient.post('/users/me/delete/', payload)
}
