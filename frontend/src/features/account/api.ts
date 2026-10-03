import { apiClient } from '@/api/client'
import type { PasswordChangePayload, TokenPair } from '@/api/types'

export async function changePassword(payload: PasswordChangePayload) {
  const { data } = await apiClient.post<TokenPair>('/users/me/password/', payload)
  return data
}
