import { CircleAlertIcon, LockIcon, SearchXIcon } from 'lucide-react'

import { HTTP_STATUS } from '@/api/constants'
import { parseApiError } from '@/api/errors'
import { EmptyState } from '@/components/EmptyState'
import { Button } from '@/components/ui/button'

interface ErrorStateProps {
  error: unknown
  onRetry?: () => void
}

/** What a page shows when loading its data fails. A 404 reads as "not found"
 * rather than "no access": the API hides private resources that way, and the
 * UI mustn't reveal they exist. */
export function ErrorState({ error, onRetry }: ErrorStateProps) {
  const { status, formMessage } = parseApiError(error)

  if (status === HTTP_STATUS.notFound) {
    return (
      <EmptyState
        icon={SearchXIcon}
        title="Not found"
        description="It may have been deleted, or the link may be wrong."
      />
    )
  }
  if (status === HTTP_STATUS.forbidden) {
    return <ForbiddenState />
  }
  return (
    <EmptyState
      icon={CircleAlertIcon}
      title="Something went wrong"
      description={formMessage}
      action={
        onRetry && (
          <Button variant="outline" onClick={onRetry}>
            Try again
          </Button>
        )
      }
    />
  )
}

export function ForbiddenState() {
  return (
    <EmptyState
      icon={LockIcon}
      title="You don't have access"
      description="Ask your organization admin if you need this."
    />
  )
}
