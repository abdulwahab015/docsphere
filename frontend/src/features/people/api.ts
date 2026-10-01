import { apiClient } from '@/api/client'
import type { ListParams, RosterUser, Paginated } from '@/api/types'

export async function listPeople({ page, search }: ListParams) {
  const { data } = await apiClient.get<Paginated<RosterUser>>('/users/', {
    params: { page, search: search || undefined },
  })
  return data
}
