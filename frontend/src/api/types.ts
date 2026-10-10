import type { components, operations } from '@/api/schema'

type Schemas = components['schemas']

export type CurrentUser = Schemas['CurrentUser']
export type CurrentUserUpdatePayload = Pick<Schemas['PatchedCurrentUser'], 'name'>
export type OrgRole = Schemas['OrgRoleEnum']
export type OrganizationSummary = Schemas['OrganizationSummary']
// The API always returns `require_two_factor`; the schema marks it optional
// only because of its model default (see `Project.visibility`).
export type Organization = Omit<Schemas['Organization'], 'require_two_factor'> & {
  require_two_factor: boolean
}
export type OrganizationUpdatePayload = Pick<
  Schemas['PatchedOrganization'],
  'name' | 'billing_email' | 'require_two_factor'
>
export type ActiveSubscription = Schemas['ActiveSubscription']
export type Price = Schemas['Price']
export type CheckoutSessionResponse = Schemas['CheckoutSessionResponse']
export type BillingPortalSessionResponse = Schemas['BillingPortalSessionResponse']
// Admins also receive `org_role` and `created`; members get only `id` and `email`.
export type RosterUser = Schemas['RosterUser']
export type AccessLevel = Schemas['AccessLevelEnum']
export type Visibility = Schemas['VisibilityEnum']
// The API always returns `visibility`. The schema marks it optional only
// because the field has a model default (so it may be omitted when
// creating), and drf-spectacular carries that into the response type.
export type Project = Omit<Schemas['Project'], 'visibility'> & { visibility: Visibility }
export type ProjectCreatePayload = Pick<Schemas['Project'], 'name' | 'description' | 'visibility'>
export type ProjectUpdatePayload = Pick<
  Schemas['PatchedProject'],
  'name' | 'description' | 'visibility'
>
// Same default-value quirk as `Project.visibility`.
export type Document = Omit<Schemas['Document'], 'visibility'> & { visibility: Visibility }
// A row of the documents list: no content, but an excerpt of where a search
// matched it. Same default-value quirk as `Project.visibility`.
export type DocumentListItem = Omit<Schemas['DocumentList'], 'visibility'> & {
  visibility: Visibility
}
export type ExcerptSegment = Schemas['ExcerptSegment']
// A document's history: one entry per revision, without and with its text.
export type DocumentVersion = Schemas['DocumentVersion']
export type DocumentVersionDetail = Schemas['DocumentVersionDetail']
// A file attached to a document, as listed (the file itself is downloaded).
export type Attachment = Schemas['Attachment']
export type DocumentCreatePayload = Pick<
  Schemas['DocumentCreate'],
  'title' | 'content' | 'visibility' | 'project'
>
export type DocumentUpdatePayload = Pick<
  Schemas['PatchedDocument'],
  'title' | 'content' | 'visibility' | 'base_revision'
>
export type ProjectPermission = Schemas['ProjectPermission']
export type DocumentPermission = Schemas['DocumentPermission']
/** One person's access to a project or document; only the shared fields are used. */
export type Grant = ProjectPermission | DocumentPermission
export type SharePayload = Schemas['Share']
export type AccessRequest = Schemas['DocumentAccessRequest']
export type AccessRequestStatus = Schemas['DocumentAccessRequestStatusEnum']
export type TokenPair = Schemas['TokenPair']
export type LoginPayload = Schemas['Login']
// A login answers with a token pair, or - for an account with two-factor
// sign-in on - a token for the code step.
export type LoginResult = Schemas['LoginResult']
export type TwoFactorChallenge = Schemas['TwoFactorChallenge']
export type TwoFactorLoginPayload = Schemas['TwoFactorLogin']
export type TwoFactorStatus = Schemas['TwoFactorStatus']
export type TwoFactorSetup = Schemas['TwoFactorSetup']
export type TwoFactorConfirmPayload = Schemas['TwoFactorConfirm']
export type RecoveryCodes = Schemas['RecoveryCodes']
export type CurrentPasswordPayload = Schemas['CurrentPassword']
export type OrganizationSignupPayload = Schemas['OrganizationSignup']
export type PasswordResetRequestPayload = Schemas['PasswordResetRequest']
export type PasswordResetConfirmPayload = Schemas['PasswordResetConfirm']
export type PasswordChangePayload = Schemas['PasswordChange']
export type EmailVerificationPayload = Schemas['EmailVerification']
export type EmailChangeRequestPayload = Schemas['EmailChangeRequest']
export type AccountDeletionPayload = Schemas['AccountDeletion']
export type OrganizationDeletionPayload = Schemas['OrganizationDeletion']
export type EmailChangeConfirmPayload = Schemas['EmailChangeConfirm']
export type InvitationAcceptPayload = Schemas['InvitationAccept']
// The invitation serializer is named for creating, but also lists and resends.
export type Invitation = Schemas['InvitationCreate']
export type InvitationStatus = Schemas['InvitationCreateStatusEnum']
export type InvitationBulkResult = Schemas['InvitationBulkResult']
// What admins see of a member: `RosterUser` narrowed to its admin shape.
export type UserDetail = Schemas['UserDetail']
// How many live projects/documents a member is the only active Owner of.
export type SoleOwnership = Schemas['SoleOwnership']
// One entry in the organization's activity (the audit log), for admins.
export type AuditEvent = Schemas['AuditEvent']
export type AuditVerb = Schemas['AuditVerbEnum']
// What the bell in the top bar lists: something the signed-in user should know about.
export type Notification = Schemas['Notification']
export type NotificationVerb = Schemas['NotificationVerbEnum']
export type UnreadCount = Schemas['UnreadCount']
export type AuditKind = NonNullable<
  NonNullable<operations['api_v1_audit_events_list']['parameters']['query']>['kind']
>

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
