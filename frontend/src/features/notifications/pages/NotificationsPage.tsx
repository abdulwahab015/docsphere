import { BellIcon, CheckCheckIcon } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { PageHeader } from '@/components/PageHeader'
import { Pagination } from '@/components/Pagination'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { describeNotification } from '@/features/notifications/describe'
import {
  useMarkAllNotificationsRead,
  useNotifications,
  useOpenNotification,
  useUnreadNotificationCount,
} from '@/features/notifications/hooks'
import { useListParams } from '@/hooks/use-list-params'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

/** Every notification the signed-in user has had (they're kept 90 days),
 * newest first - the bell shows only the latest. */
export function NotificationsPage() {
  const { page, setPage } = useListParams()
  const notifications = useNotifications({ page })
  const unreadCount = useUnreadNotificationCount()
  const markAllRead = useMarkAllNotificationsRead()
  const openNotification = useOpenNotification()

  return (
    <>
      <PageHeader
        title="Notifications"
        description="What's been shared with you and what's happened to your edit requests, from the last 90 days."
        actions={
          Boolean(unreadCount.data) && (
            <Button
              variant="outline"
              disabled={markAllRead.isPending}
              onClick={() => markAllRead.mutate()}
            >
              <CheckCheckIcon aria-hidden />
              Mark all as read
            </Button>
          )
        }
      />
      {notifications.isError ? (
        <ErrorState error={notifications.error} onRetry={() => void notifications.refetch()} />
      ) : !notifications.data ? (
        <Skeleton className="h-40 w-full" aria-label="Loading notifications" />
      ) : !notifications.data.count ? (
        <EmptyState
          icon={BellIcon}
          title="No notifications yet"
          description="You'll be told here when something is shared with you or someone asks to edit your document."
        />
      ) : (
        <>
          <ul aria-label="Notifications" className="flex flex-col divide-y rounded-lg border">
            {notifications.data.results.map((notification) => (
              <li key={notification.id}>
                <button
                  type="button"
                  onClick={() => openNotification(notification)}
                  className="flex w-full flex-col gap-0.5 px-3 py-2 text-left text-sm hover:bg-muted focus-visible:bg-muted focus-visible:outline-none"
                >
                  <span
                    className={cn('[overflow-wrap:anywhere]', !notification.read && 'font-medium')}
                  >
                    {!notification.read && <span className="sr-only">Unread: </span>}
                    {describeNotification(notification)}
                  </span>
                  <span className="text-muted-foreground">
                    {formatDateTime(notification.created)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <Pagination page={page} count={notifications.data.count} onPageChange={setPage} />
        </>
      )}
    </>
  )
}
