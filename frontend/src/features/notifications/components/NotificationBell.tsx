import { BellIcon, CheckCheckIcon } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'

import type { Notification } from '@/api/types'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { describeNotification, notificationLink } from '@/features/notifications/describe'
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
  useUnreadNotificationCount,
} from '@/features/notifications/hooks'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

// Beyond this the badge just says there are many.
const MAX_BADGE_COUNT = 9

/** The top bar's bell: how many notifications are unread, and a menu of the
 * latest. Opening one marks it read and goes to what it's about. */
export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const unreadCount = useUnreadNotificationCount()
  const notifications = useNotifications(open)
  const markRead = useMarkNotificationRead()
  const markAllRead = useMarkAllNotificationsRead()
  const navigate = useNavigate()
  const unread = unreadCount.data ?? 0

  const openNotification = (notification: Notification) => {
    if (!notification.read) {
      markRead.mutate(notification.id)
    }
    const link = notificationLink(notification)
    if (link) {
      void navigate(link)
    }
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative"
          aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        >
          <BellIcon aria-hidden />
          {unread > 0 && (
            <span
              aria-hidden
              className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-white"
            >
              {unread > MAX_BADGE_COUNT ? `${MAX_BADGE_COUNT}+` : unread}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 max-w-[calc(100vw-2rem)]">
        <DropdownMenuLabel>Notifications</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {notifications.isError ? (
          <DropdownMenuItem disabled>Couldn't load your notifications.</DropdownMenuItem>
        ) : !notifications.data ? (
          <DropdownMenuItem disabled>Loading notifications…</DropdownMenuItem>
        ) : !notifications.data.count ? (
          <DropdownMenuItem disabled>Nothing yet.</DropdownMenuItem>
        ) : (
          <DropdownMenuGroup className="max-h-96 overflow-y-auto">
            {notifications.data.results.map((notification) => (
              <DropdownMenuItem
                key={notification.id}
                className="flex flex-col items-start gap-0.5"
                onSelect={() => openNotification(notification)}
              >
                <span
                  className={cn(
                    '[overflow-wrap:anywhere] whitespace-normal',
                    !notification.read && 'font-medium',
                  )}
                >
                  {!notification.read && <span className="sr-only">Unread: </span>}
                  {describeNotification(notification)}
                </span>
                <span className="text-xs text-muted-foreground">
                  {formatDateTime(notification.created)}
                </span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
        )}
        {unread > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              disabled={markAllRead.isPending}
              onSelect={() => markAllRead.mutate()}
            >
              <CheckCheckIcon aria-hidden />
              Mark all as read
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
