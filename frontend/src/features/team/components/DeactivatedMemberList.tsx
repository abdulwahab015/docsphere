import { UserXIcon } from 'lucide-react'
import { toast } from 'sonner'

import { actionErrorMessage } from '@/api/errors'
import type { UserDetail } from '@/api/types'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { Pagination } from '@/components/Pagination'
import { SearchInput } from '@/components/SearchInput'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useDeactivatedUsers, useReactivateUser } from '@/features/team/hooks'
import { useListParams } from '@/hooks/use-list-params'
import { ORG_ROLE_LABELS } from '@/lib/access'

const LOADING_ROWS = 3
const COLUMN_COUNT = 3

/** People an admin deactivated; reactivating one lets them log in again. */
export function DeactivatedMemberList() {
  const { page, search, setPage, setSearch } = useListParams()
  const deactivated = useDeactivatedUsers({ page, search })
  const reactivate = useReactivateUser()

  const reactivateMember = ({ id, email }: UserDetail) =>
    reactivate.mutate(id, {
      onSuccess: () => toast.success(`Reactivated ${email}. They can log in again.`),
      onError: (error) => toast.error(actionErrorMessage(error, `Couldn't reactivate ${email}.`)),
    })

  return (
    <>
      <SearchInput
        value={search}
        onSearch={setSearch}
        label="Search deactivated people"
        placeholder="Search by email"
      />
      {deactivated.isError ? (
        <ErrorState error={deactivated.error} onRetry={() => void deactivated.refetch()} />
      ) : deactivated.data && !deactivated.data.count ? (
        <EmptyState
          icon={UserXIcon}
          title={search ? 'No matches' : 'No one is deactivated'}
          description={
            search
              ? `No deactivated person's email matches "${search}".`
              : 'People you deactivate show up here, ready to be reactivated.'
          }
        />
      ) : (
        <>
          <div className="rounded-lg border">
            <Table aria-busy={deactivated.isFetching}>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {deactivated.data
                  ? deactivated.data.results.map((member) => (
                      <TableRow key={member.id}>
                        <TableCell className="font-medium">{member.email}</TableCell>
                        <TableCell>{ORG_ROLE_LABELS[member.org_role]}</TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={reactivate.isPending}
                            onClick={() => reactivateMember(member)}
                          >
                            {reactivate.isPending && reactivate.variables === member.id && (
                              <Spinner aria-hidden />
                            )}
                            Reactivate
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  : Array.from({ length: LOADING_ROWS }, (_unused, index) => (
                      <TableRow key={index}>
                        <TableCell colSpan={COLUMN_COUNT}>
                          <Skeleton className="h-5 w-full" />
                        </TableCell>
                      </TableRow>
                    ))}
              </TableBody>
            </Table>
          </div>
          {deactivated.data && (
            <Pagination page={page} count={deactivated.data.count} onPageChange={setPage} />
          )}
        </>
      )}
    </>
  )
}
