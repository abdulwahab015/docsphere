import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'

import type { Notification } from '@/api/types'

import {
  fetchUnreadCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/features/notifications/api'
import { notificationLink } from '@/features/notifications/describe'
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

/** A page of notifications - in the bell, only while its menu is open. */
export function useNotifications({ page, enabled = true }: { page: number; enabled?: boolean }) {
  return useQuery({
    queryKey: notificationKeys.list(page),
    queryFn: () => listNotifications(page),
    enabled,
    staleTime: 0,
    placeholderData: keepPreviousData,
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

/** Opening a notification, from the bell or the page: marks it read if it
 * wasn't, and goes to what it's about when there's somewhere to go. */
export function useOpenNotification() {
  const markRead = useMarkNotificationRead()
  const navigate = useNavigate()
  return (notification: Notification) => {
    if (!notification.read) {
      markRead.mutate(notification.id)
    }
    const link = notificationLink(notification)
    if (link) {
      void navigate(link)
    }
  }
}
