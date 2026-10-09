import { apiClient } from '@/api/client'
import type {
  CurrentPasswordPayload,
  RecoveryCodes,
  TwoFactorConfirmPayload,
  TwoFactorSetup,
  TwoFactorStatus,
} from '@/api/types'

const TWO_FACTOR_PATH = '/users/me/two-factor/'

export async function fetchTwoFactorStatus() {
  const { data } = await apiClient.get<TwoFactorStatus>(TWO_FACTOR_PATH)
  return data
}

/** A new key for the authenticator app; nothing changes at sign-in until a
 * code from the app confirms it. */
export async function startTwoFactorSetup() {
  const { data } = await apiClient.post<TwoFactorSetup>(`${TWO_FACTOR_PATH}setup/`)
  return data
}

/** Turns two-factor sign-in on and returns the first recovery codes. */
export async function confirmTwoFactor(payload: TwoFactorConfirmPayload) {
  const { data } = await apiClient.post<RecoveryCodes>(`${TWO_FACTOR_PATH}confirm/`, payload)
  return data
}

export async function turnOffTwoFactor(payload: CurrentPasswordPayload) {
  await apiClient.post(`${TWO_FACTOR_PATH}disable/`, payload)
}

/** A new set of recovery codes; the old ones stop working. */
export async function makeNewRecoveryCodes(payload: CurrentPasswordPayload) {
  const { data } = await apiClient.post<RecoveryCodes>(`${TWO_FACTOR_PATH}recovery-codes/`, payload)
  return data
}
