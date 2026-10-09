import { apiClient } from '@/api/client'
import type { Notification, Paginated, UnreadCount } from '@/api/types'

const NOTIFICATIONS_PATH = '/notifications/'

/** The newest page of the signed-in user's notifications. */
export async function listNotifications() {
  const { data } = await apiClient.get<Paginated<Notification>>(NOTIFICATIONS_PATH)
  return data
}

export async function fetchUnreadCount() {
  const { data } = await apiClient.get<UnreadCount>(`${NOTIFICATIONS_PATH}unread-count/`)
  return data.count
}

export async function markNotificationRead(notificationId: number) {
  await apiClient.post(`${NOTIFICATIONS_PATH}${notificationId}/read/`)
}

export async function markAllNotificationsRead() {
  await apiClient.post(`${NOTIFICATIONS_PATH}read-all/`)
}
