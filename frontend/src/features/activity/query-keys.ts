import type { ActivityParams } from '@/features/activity/api'

export const activityKeys = {
  all: ['activity'] as const,
  list: (params: ActivityParams) => [...activityKeys.all, 'list', params] as const,
}
