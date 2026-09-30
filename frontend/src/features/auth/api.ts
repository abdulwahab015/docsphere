import { apiClient } from '@/api/client'
import type {
  CurrentUser,
  InvitationAcceptPayload,
  LoginPayload,
  OrganizationSignupPayload,
  PasswordResetConfirmPayload,
  PasswordResetRequestPayload,
  TokenPair,
} from '@/api/types'

export async function login(payload: LoginPayload) {
  const { data } = await apiClient.post<TokenPair>('/users/auth/login/', payload)
  return data
}

export async function logout() {
  // The refresh token to blacklist travels in the HttpOnly cookie.
  await apiClient.post('/users/auth/logout/', {})
}

export async function signupOrganization(payload: OrganizationSignupPayload) {
  const { data } = await apiClient.post<TokenPair>('/organizations/signup/', payload)
  return data
}

export async function acceptInvitation(payload: InvitationAcceptPayload) {
  const { data } = await apiClient.post<TokenPair>('/users/invitations/accept/', payload)
  return data
}

export async function requestPasswordReset(payload: PasswordResetRequestPayload) {
  await apiClient.post('/users/auth/password-reset/', payload)
}

export async function confirmPasswordReset(payload: PasswordResetConfirmPayload) {
  await apiClient.post('/users/auth/password-reset/confirm/', payload)
}

export async function fetchCurrentUser() {
  const { data } = await apiClient.get<CurrentUser>('/users/me/')
  return data
}
