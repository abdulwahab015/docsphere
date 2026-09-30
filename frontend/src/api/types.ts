import type { components } from '@/api/schema'

type Schemas = components['schemas']

export type CurrentUser = Schemas['CurrentUser']
export type OrgRole = Schemas['OrgRoleEnum']
export type TokenPair = Schemas['TokenPair']
export type LoginPayload = Schemas['Login']
export type OrganizationSignupPayload = Schemas['OrganizationSignup']
export type PasswordResetRequestPayload = Schemas['PasswordResetRequest']
export type PasswordResetConfirmPayload = Schemas['PasswordResetConfirm']
export type InvitationAcceptPayload = Schemas['InvitationAccept']
