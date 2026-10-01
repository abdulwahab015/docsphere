import { apiClient } from '@/api/client'
import type {
  Invitation,
  InvitationBulkResult,
  ListParams,
  OrgRole,
  Paginated,
  UserDetail,
} from '@/api/types'

// Every endpoint here is admin-only.
const USERS_PATH = '/users/'
const INVITATIONS_PATH = `${USERS_PATH}invitations/`

function userPath(userId: number) {
  return `${USERS_PATH}${userId}/`
}

function invitationPath(invitationId: number) {
  return `${INVITATIONS_PATH}${invitationId}/`
}

export async function changeRole(userId: number, orgRole: OrgRole) {
  const { data } = await apiClient.patch<UserDetail>(`${userPath(userId)}role/`, {
    org_role: orgRole,
  })
  return data
}

/** Signs the user out and stops them logging in, until they're reactivated. */
export async function deactivateUser(userId: number) {
  await apiClient.delete(`${userPath(userId)}deactivate/`)
}

export async function listDeactivatedUsers({ page, search }: ListParams) {
  const { data } = await apiClient.get<Paginated<UserDetail>>(`${USERS_PATH}deactivated/`, {
    params: { page, search: search || undefined },
  })
  return data
}

export async function reactivateUser(userId: number) {
  const { data } = await apiClient.post<UserDetail>(`${userPath(userId)}reactivate/`)
  return data
}

/** Every invitation the organization has sent, newest first. */
export async function listInvitations(page: number) {
  const { data } = await apiClient.get<Paginated<Invitation>>(INVITATIONS_PATH, {
    params: { page },
  })
  return data
}

export async function createInvitation(email: string) {
  const { data } = await apiClient.post<Invitation>(INVITATIONS_PATH, { email })
  return data
}

/** Invites every address in the first column of an .xlsx file. */
export async function bulkInvite(file: File) {
  const body = new FormData()
  body.append('file', file)
  const { data } = await apiClient.post<InvitationBulkResult>(`${INVITATIONS_PATH}bulk/`, body)
  return data
}

/** Emails a new link (with a fresh expiry); the previous link stops working. */
export async function resendInvitation(invitationId: number) {
  const { data } = await apiClient.post<Invitation>(`${invitationPath(invitationId)}resend/`)
  return data
}

export async function revokeInvitation(invitationId: number) {
  await apiClient.delete(invitationPath(invitationId))
}
