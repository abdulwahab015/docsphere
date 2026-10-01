import { apiClient } from '@/api/client'
import type { Organization, OrganizationUpdatePayload } from '@/api/types'

const PROFILE_PATH = '/organizations/profile/'

export async function fetchOrganization() {
  const { data } = await apiClient.get<Organization>(PROFILE_PATH)
  return data
}

export async function updateOrganization(payload: OrganizationUpdatePayload) {
  const { data } = await apiClient.patch<Organization>(PROFILE_PATH, payload)
  return data
}
