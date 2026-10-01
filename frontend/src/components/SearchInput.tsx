import { SearchIcon } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Input } from '@/components/ui/input'

export const SEARCH_DEBOUNCE_MS = 300

interface SearchInputProps {
  value: string
  onSearch: (search: string) => void
  label: string
  placeholder?: string
}

/** A search box that reports what was typed once typing pauses, so a list
 * isn't re-fetched on every keystroke. */
export function SearchInput({ value, onSearch, label, placeholder }: SearchInputProps) {
  const [draft, setDraft] = useState(value)
  const [committedValue, setCommittedValue] = useState(value)

  // Follow outside changes too (e.g. navigating back to an older search).
  if (value !== committedValue) {
    setCommittedValue(value)
    setDraft(value)
  }

  useEffect(() => {
    const search = draft.trim()
    if (search === value) {
      return undefined
    }
    const timer = setTimeout(() => onSearch(search), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [draft, value, onSearch])

  return (
    <div className="relative w-full max-w-sm">
      <SearchIcon
        className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
      <Input
        type="search"
        aria-label={label}
        placeholder={placeholder}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        className="pl-8"
      />
    </div>
  )
}
