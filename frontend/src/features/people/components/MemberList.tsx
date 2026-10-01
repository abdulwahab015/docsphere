import { UsersIcon } from 'lucide-react'

import type { RosterUser } from '@/api/types'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
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
import { MemberActions } from '@/features/team/components/MemberActions'
import { useListParams } from '@/hooks/use-list-params'
import { ORG_ROLE_LABELS } from '@/lib/access'
import { formatDate } from '@/lib/format'

const LOADING_ROWS = 5
const ADMIN_COLUMN_COUNT = 4

/** The organization's active members. Admins also get each member's role and
 * join date (the API only sends those to admins), and a menu to manage them. */
export function MemberList() {
  const user = useSignedInMember()
  const { page, search, setPage, setSearch } = useListParams()
  const people = usePeople({ page, search })
  const isAdmin = user.org_role === 'ADMIN'

  return (
    <>
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
                  {isAdmin && (
                    <>
                      <TableHead>Role</TableHead>
                      <TableHead>Joined</TableHead>
                      <TableHead>
                        <span className="sr-only">Actions</span>
                      </TableHead>
                    </>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {people.data
                  ? people.data.results.map((person) => (
                      <MemberRow key={person.id} person={person} isYou={person.id === user.id} />
                    ))
                  : Array.from({ length: LOADING_ROWS }, (_unused, index) => (
                      <TableRow key={index}>
                        <TableCell colSpan={isAdmin ? ADMIN_COLUMN_COUNT : 1}>
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

function MemberRow({ person, isYou }: { person: RosterUser; isYou: boolean }) {
  return (
    <TableRow>
      <TableCell>
        <div className="flex items-center gap-2">
          {person.email}
          {isYou && <Badge variant="secondary">You</Badge>}
        </div>
      </TableCell>
      {/* Only an admin's roster carries the role, so it doubles as the admin check. */}
      {'org_role' in person && (
        <>
          <TableCell>{ORG_ROLE_LABELS[person.org_role]}</TableCell>
          <TableCell className="text-muted-foreground">{formatDate(person.created)}</TableCell>
          <TableCell className="text-right">
            {!isYou && <MemberActions member={person} />}
          </TableCell>
        </>
      )}
    </TableRow>
  )
}
