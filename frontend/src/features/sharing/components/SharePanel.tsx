import { useId, useState } from 'react'

import { DEFAULT_PAGE_SIZE } from '@/api/constants'
import { ErrorState } from '@/components/ErrorState'
import { Pagination } from '@/components/Pagination'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import type { SharedResource } from '@/features/sharing/api'
import { AddPersonForm } from '@/features/sharing/components/AddPersonForm'
import { GrantRow } from '@/features/sharing/components/GrantRow'
import { useGrants } from '@/features/sharing/hooks'

const FIRST_PAGE = 1

interface SharePanelProps {
  resource: SharedResource
  isPublic: boolean
  /** Called once the signed-in user no longer manages the resource's sharing. */
  onSharingGivenUp: () => void
}

export function SharePanel({ resource, isPublic, onSharingGivenUp }: SharePanelProps) {
  const headingId = useId()
  const [page, setPage] = useState(FIRST_PAGE)
  const grants = useGrants(resource, page)
  const grantedUserIds = new Set(grants.data?.results.map((grant) => grant.user))

  // Removing the only person on a later page would leave that page empty.
  const onRevoked = () => {
    if (page > FIRST_PAGE && grants.data?.results.length === 1) {
      setPage(page - 1)
    }
  }

  return (
    <>
      <AddPersonForm resource={resource} grantedUserIds={grantedUserIds} />
      <Separator />
      <section className="flex flex-col gap-3">
        <h3 id={headingId} className="text-sm font-medium">
          People with access
        </h3>
        {grants.isError ? (
          <ErrorState error={grants.error} onRetry={() => void grants.refetch()} />
        ) : !grants.data ? (
          <Skeleton className="h-24 w-full" aria-label="Loading people with access" />
        ) : (
          <ul aria-labelledby={headingId} aria-busy={grants.isFetching} className="divide-y">
            {grants.data.results.map((grant) => (
              <GrantRow
                key={grant.id}
                resource={resource}
                grant={grant}
                isPublic={isPublic}
                onSharingGivenUp={onSharingGivenUp}
                onRevoked={onRevoked}
              />
            ))}
          </ul>
        )}
        {grants.data && grants.data.count > DEFAULT_PAGE_SIZE && (
          <Pagination page={page} count={grants.data.count} onPageChange={setPage} />
        )}
      </section>
    </>
  )
}
