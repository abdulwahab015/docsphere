import { ActivityIcon } from 'lucide-react'
import { useId } from 'react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { PageHeader } from '@/components/PageHeader'
import { Pagination } from '@/components/Pagination'
import { SearchInput } from '@/components/SearchInput'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Skeleton } from '@/components/ui/skeleton'
import { useSignedInMember } from '@/features/auth/hooks'
import {
  ACTIVITY_KIND_LABELS,
  ACTIVITY_KINDS,
  actorName,
  describeEvent,
} from '@/features/activity/describe'
import { type ActivityFilter, useActivity, useActivityFilters } from '@/features/activity/hooks'
import { useListParams } from '@/hooks/use-list-params'
import { formatDateTime } from '@/lib/format'

/** The organization's activity, for its admins: who changed access and
 * membership, deleted or restored something, or attached or deleted a
 * file. Newest first, narrowed by person, kind and days. */
export function ActivityPage() {
  const { organization } = useSignedInMember()
  const { page, search, setPage, setSearch } = useListParams()
  const { kind, from, to, setFilter } = useActivityFilters()
  const activity = useActivity({ page, search, kind, from, to })
  const isFiltered = Boolean(search || kind || from || to)

  return (
    <>
      <PageHeader
        title="Activity"
        description={`Who changed access and membership, deleted and restored things, and attached files in ${organization.name}. Kept for a year. Private projects and documents you can't open aren't named.`}
      />
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1">
          <SearchInput
            value={search}
            onSearch={setSearch}
            label="Search activity"
            placeholder="Search by name or email"
          />
        </div>
        <KindFilter value={kind} onChange={(value) => setFilter('kind', value)} />
        <DayFilter label="From" filter="from" value={from} onChange={setFilter} />
        <DayFilter label="To" filter="to" value={to} onChange={setFilter} />
      </div>
      {activity.isError ? (
        <ErrorState error={activity.error} onRetry={() => void activity.refetch()} />
      ) : !activity.data ? (
        <Skeleton className="h-40 w-full" aria-label="Loading activity" />
      ) : !activity.data.count ? (
        <EmptyState
          icon={ActivityIcon}
          title={isFiltered ? 'No matching activity' : 'No activity yet'}
          description={
            isFiltered
              ? 'Nothing matches these filters.'
              : 'Sharing, membership changes, deletes and restores, and attached files show up here.'
          }
        />
      ) : (
        <>
          <ul
            aria-label="Activity"
            aria-busy={activity.isFetching}
            className="flex flex-col divide-y rounded-lg border"
          >
            {activity.data.results.map((event) => (
              <li key={event.id} className="flex flex-col gap-0.5 px-3 py-2 text-sm">
                <span className="[overflow-wrap:anywhere]">{describeEvent(event)}</span>
                <span className="[overflow-wrap:anywhere] text-muted-foreground">
                  {actorName(event)} · {formatDateTime(event.created)}
                </span>
              </li>
            ))}
          </ul>
          <Pagination page={page} count={activity.data.count} onPageChange={setPage} />
        </>
      )}
    </>
  )
}

interface KindFilterProps {
  value: string
  onChange: (kind: string) => void
}

function KindFilter({ value, onChange }: KindFilterProps) {
  const id = useId()

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>Kind</Label>
      <NativeSelect id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        <NativeSelectOption value="">All kinds</NativeSelectOption>
        {ACTIVITY_KINDS.map((kind) => (
          <NativeSelectOption key={kind} value={kind}>
            {ACTIVITY_KIND_LABELS[kind]}
          </NativeSelectOption>
        ))}
      </NativeSelect>
    </div>
  )
}

interface DayFilterProps {
  label: string
  filter: ActivityFilter
  value: string
  onChange: (filter: ActivityFilter, day: string) => void
}

/** One end of the range of days, inclusive. */
function DayFilter({ label, filter, value, onChange }: DayFilterProps) {
  const id = useId()

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type="date"
        className="w-auto"
        value={value}
        onChange={(event) => onChange(filter, event.target.value)}
      />
    </div>
  )
}
