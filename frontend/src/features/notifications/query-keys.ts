export const notificationKeys = {
  all: ['notifications'] as const,
  list: (page: number) => [...notificationKeys.all, 'list', page] as const,
  unreadCount: () => [...notificationKeys.all, 'unread-count'] as const,
}
