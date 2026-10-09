import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  fetchUnreadCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/features/notifications/api'
import { notificationKeys } from '@/features/notifications/query-keys'

/** How often the unread count is asked for while the app is open. */
export const NOTIFICATION_POLL_MS = 30_000

/** The badge's count: polled, and asked again whenever the tab comes back
 * into focus, so new notifications show up without a reload. */
export function useUnreadNotificationCount() {
  return useQuery({
    queryKey: notificationKeys.unreadCount(),
    queryFn: fetchUnreadCount,
    refetchInterval: NOTIFICATION_POLL_MS,
    refetchOnWindowFocus: 'always',
  })
}

/** The list itself, loaded only while the menu is open. */
export function useNotifications(enabled: boolean) {
  return useQuery({
    queryKey: notificationKeys.list(),
    queryFn: listNotifications,
    enabled,
    staleTime: 0,
  })
}

function useInvalidateNotifications() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: notificationKeys.all })
}

export function useMarkNotificationRead() {
  const invalidate = useInvalidateNotifications()
  return useMutation({ mutationFn: markNotificationRead, onSuccess: invalidate })
}

export function useMarkAllNotificationsRead() {
  const invalidate = useInvalidateNotifications()
  return useMutation({ mutationFn: markAllNotificationsRead, onSuccess: invalidate })
}
