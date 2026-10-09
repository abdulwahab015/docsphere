import { BellIcon, CheckCheckIcon, ListIcon } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'

import { PATHS } from '@/app/paths'

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
import { describeNotification } from '@/features/notifications/describe'
import {
  useMarkAllNotificationsRead,
  useNotifications,
  useOpenNotification,
  useUnreadNotificationCount,
} from '@/features/notifications/hooks'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

const FIRST_PAGE = 1
// Beyond this the badge just says there are many.
const MAX_BADGE_COUNT = 9

/** The top bar's bell: how many notifications are unread, and a menu of the
 * latest. Opening one marks it read and goes to what it's about. */
export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const unreadCount = useUnreadNotificationCount()
  const notifications = useNotifications({ page: FIRST_PAGE, enabled: open })
  const markAllRead = useMarkAllNotificationsRead()
  const openNotification = useOpenNotification()
  const navigate = useNavigate()
  const unread = unreadCount.data ?? 0

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
        <DropdownMenuSeparator />
        {unread > 0 && (
          <DropdownMenuItem disabled={markAllRead.isPending} onSelect={() => markAllRead.mutate()}>
            <CheckCheckIcon aria-hidden />
            Mark all as read
          </DropdownMenuItem>
        )}
        <DropdownMenuItem onSelect={() => void navigate(PATHS.notifications)}>
          <ListIcon aria-hidden />
          See all notifications
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
