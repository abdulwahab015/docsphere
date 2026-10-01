import type { components } from '@/api/schema'

type Schemas = components['schemas']

export type CurrentUser = Schemas['CurrentUser']
export type OrgRole = Schemas['OrgRoleEnum']
export type OrganizationSummary = Schemas['OrganizationSummary']
export type Organization = Schemas['Organization']
export type OrganizationUpdatePayload = Pick<
  Schemas['PatchedOrganization'],
  'name' | 'billing_email'
>
export type ActiveSubscription = Schemas['ActiveSubscription']
// Admins also receive `org_role` and `created`; members get only `id` and `email`.
export type RosterUser = Schemas['RosterUser']
export type TokenPair = Schemas['TokenPair']
export type LoginPayload = Schemas['Login']
export type OrganizationSignupPayload = Schemas['OrganizationSignup']
export type PasswordResetRequestPayload = Schemas['PasswordResetRequest']
export type PasswordResetConfirmPayload = Schemas['PasswordResetConfirm']
export type InvitationAcceptPayload = Schemas['InvitationAccept']

/** DRF's page-number pagination envelope, shared by every list endpoint. */
export interface Paginated<TItem> {
  count: number
  next?: string | null
  previous?: string | null
  results: TItem[]
}

export interface ListParams {
  page: number
  search: string
}
