import type { ListParams } from '@/api/types'

export const teamKeys = {
  all: ['team'] as const,
  invitations: () => [...teamKeys.all, 'invitations'] as const,
  invitationsPage: (page: number) => [...teamKeys.invitations(), page] as const,
  deactivated: () => [...teamKeys.all, 'deactivated'] as const,
  deactivatedList: (params: ListParams) => [...teamKeys.deactivated(), params] as const,
}
