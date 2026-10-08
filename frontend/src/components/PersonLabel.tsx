import { displayName, type Person } from '@/lib/people'

interface PersonLabelProps {
  person: Person
  /** Shown after the name, muted, e.g. "(you)". */
  note?: string
}

/** A person in a list: their name with their email address beneath it, or
 * just the address while they haven't given a name. */
export function PersonLabel({ person, note }: PersonLabelProps) {
  return (
    <span className="flex min-w-0 flex-col">
      <span className="truncate font-medium">
        {displayName(person)}
        {note && <span className="font-normal text-muted-foreground"> {note}</span>}
      </span>
      {person.name && (
        <span className="truncate text-xs text-muted-foreground">{person.email}</span>
      )}
    </span>
  )
}
