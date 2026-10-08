import { useId, useState } from 'react'
import { toast } from 'sonner'

import { actionErrorMessage } from '@/api/errors'
import type { AccessLevel, RosterUser } from '@/api/types'
import { ErrorState } from '@/components/ErrorState'
import { PersonLabel } from '@/components/PersonLabel'
import { SearchInput } from '@/components/SearchInput'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { usePeopleSearch } from '@/features/people/hooks'
import type { SharedResource } from '@/features/sharing/api'
import { AccessLevelSelect } from '@/features/sharing/components/AccessLevelSelect'
import { useShareResource } from '@/features/sharing/hooks'
import { ACCESS_LEVEL_DESCRIPTIONS, ACCESS_LEVEL_LABELS } from '@/lib/access'
import { displayName } from '@/lib/people'

interface AddPersonFormProps {
  resource: SharedResource
  /** People already listed with access, who are marked rather than offered. */
  grantedUserIds: ReadonlySet<number>
}

/** Finds people in the organization by email and gives them the chosen level. */
export function AddPersonForm({ resource, grantedUserIds }: AddPersonFormProps) {
  const levelId = useId()
  const [search, setSearch] = useState('')
  const [level, setLevel] = useState<AccessLevel>('VIEWER')
  const people = usePeopleSearch(search)
  const share = useShareResource(resource)

  const addPerson = (person: RosterUser) => {
    const who = displayName(person)
    share.mutate(
      { user: person.id, access_level: level },
      {
        onSuccess: (grant) =>
          toast.success(`${who} now has ${ACCESS_LEVEL_LABELS[grant.access_level]} access.`),
        onError: (error) => toast.error(actionErrorMessage(error, `Couldn't share with ${who}.`)),
      },
    )
  }

  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-sm font-medium">Add people</h3>
      <div className="flex flex-wrap items-center gap-3">
        <SearchInput
          value={search}
          onSearch={setSearch}
          label="Search people by name or email"
          placeholder="Search people by name or email"
        />
        <div className="flex items-center gap-2">
          <Label htmlFor={levelId}>Add as</Label>
          <AccessLevelSelect id={levelId} value={level} onChange={setLevel} />
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        {ACCESS_LEVEL_LABELS[level]}: {ACCESS_LEVEL_DESCRIPTIONS[level]}
      </p>
      {search &&
        (people.isError ? (
          <ErrorState error={people.error} onRetry={() => void people.refetch()} />
        ) : !people.data ? (
          <Skeleton className="h-16 w-full" aria-label="Searching people" />
        ) : !people.data.count ? (
          <p className="text-sm text-muted-foreground">
            No one in your organization matches &ldquo;{search}&rdquo;.
          </p>
        ) : (
          <>
            <ul aria-label="Matching people" className="divide-y">
              {people.data.results.map((person) => (
                <li key={person.id} className="flex items-center gap-3 py-2">
                  <span className="min-w-0 flex-1 text-sm">
                    <PersonLabel person={person} />
                  </span>
                  {grantedUserIds.has(person.id) ? (
                    <span className="text-xs text-muted-foreground">Has access</span>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      aria-label={`Add ${displayName(person)}`}
                      disabled={share.isPending}
                      onClick={() => addPerson(person)}
                    >
                      {share.isPending && share.variables.user === person.id && (
                        <Spinner aria-hidden />
                      )}
                      Add
                    </Button>
                  )}
                </li>
              ))}
            </ul>
            {people.data.count > people.data.results.length && (
              <p className="text-xs text-muted-foreground">
                Showing the first {people.data.results.length} of {people.data.count} matches. Keep
                typing to narrow them down.
              </p>
            )}
          </>
        ))}
    </section>
  )
}
