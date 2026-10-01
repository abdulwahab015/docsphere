import { UsersIcon } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { PageHeader } from '@/components/PageHeader'
import { Pagination } from '@/components/Pagination'
import { SearchInput } from '@/components/SearchInput'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useSignedInMember } from '@/features/auth/hooks'
import { usePeople } from '@/features/people/hooks'
import { useListParams } from '@/hooks/use-list-params'

const LOADING_ROWS = 5

export function PeoplePage() {
  const user = useSignedInMember()
  const { page, search, setPage, setSearch } = useListParams()
  const people = usePeople({ page, search })

  return (
    <>
      <PageHeader
        title="People"
        description={`Everyone in ${user.organization.name}. Share projects and documents with them.`}
      />
      <SearchInput
        value={search}
        onSearch={setSearch}
        label="Search people"
        placeholder="Search by email"
      />
      {people.isError ? (
        <ErrorState error={people.error} onRetry={() => void people.refetch()} />
      ) : people.data && !people.data.count ? (
        <EmptyState
          icon={UsersIcon}
          title={search ? 'No matches' : 'No one here yet'}
          description={search ? `No one's email matches "${search}".` : undefined}
        />
      ) : (
        <>
          <div className="rounded-lg border">
            <Table aria-busy={people.isFetching}>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {people.data
                  ? people.data.results.map((person) => (
                      <TableRow key={person.id}>
                        <TableCell className="flex items-center gap-2">
                          {person.email}
                          {person.id === user.id && <Badge variant="secondary">You</Badge>}
                        </TableCell>
                      </TableRow>
                    ))
                  : Array.from({ length: LOADING_ROWS }, (_unused, index) => (
                      <TableRow key={index}>
                        <TableCell>
                          <Skeleton className="h-5 w-64" />
                        </TableCell>
                      </TableRow>
                    ))}
              </TableBody>
            </Table>
          </div>
          {people.data && (
            <Pagination page={page} count={people.data.count} onPageChange={setPage} />
          )}
        </>
      )}
    </>
  )
}
