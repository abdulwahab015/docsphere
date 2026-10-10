import { apiClient } from '@/api/client'
import type {
  CurrentUser,
  EmailChangeConfirmPayload,
  EmailVerificationPayload,
  InvitationAcceptPayload,
  LoginPayload,
  LoginResult,
  OrganizationSignupPayload,
  PasswordResetConfirmPayload,
  PasswordResetRequestPayload,
  TokenPair,
  TwoFactorLoginPayload,
} from '@/api/types'

export async function login(payload: LoginPayload) {
  const { data } = await apiClient.post<LoginResult>('/users/auth/login/', payload)
  return data
}

export async function loginWithTwoFactor(payload: TwoFactorLoginPayload) {
  const { data } = await apiClient.post<TokenPair>('/users/auth/login/two-factor/', payload)
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

export async function verifyEmail(payload: EmailVerificationPayload) {
  await apiClient.post('/users/auth/verify-email/', payload)
}

export async function resendVerificationEmail() {
  await apiClient.post('/users/me/verification-email/')
}

export async function confirmEmailChange(payload: EmailChangeConfirmPayload) {
  await apiClient.post('/users/auth/confirm-email/', payload)
}
