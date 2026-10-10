import { apiClient } from '@/api/client'
import type {
  Organization,
  OrganizationDeletionPayload,
  OrganizationUpdatePayload,
} from '@/api/types'

const ORGANIZATIONS_PATH = '/organizations/'
const PROFILE_PATH = `${ORGANIZATIONS_PATH}profile/`

export async function fetchOrganization() {
  const { data } = await apiClient.get<Organization>(PROFILE_PATH)
  return data
}

export async function updateOrganization(payload: OrganizationUpdatePayload) {
  const { data } = await apiClient.patch<Organization>(PROFILE_PATH, payload)
  return data
}

/** Deletes the organization, confirmed by its name; it can be restored
 * until it's purged. */
export async function deleteOrganization(payload: OrganizationDeletionPayload) {
  await apiClient.post(`${ORGANIZATIONS_PATH}delete/`, payload)
}

export async function restoreOrganization() {
  await apiClient.post(`${ORGANIZATIONS_PATH}delete/cancel/`)
}

/** Asks for an export; a link to it is emailed when it's ready. */
export async function requestExport() {
  await apiClient.post(`${ORGANIZATIONS_PATH}exports/`)
}

/** The export a link's token names, as a .zip (fetched as an `arraybuffer`
 * for the same reason as attachments: jsdom's XHR can't produce a `blob`). */
export async function downloadExport(token: string) {
  const { data } = await apiClient.get<ArrayBuffer>(`${ORGANIZATIONS_PATH}exports/download/`, {
    params: { token },
    responseType: 'arraybuffer',
  })
  return new Blob([data], { type: 'application/zip' })
}
