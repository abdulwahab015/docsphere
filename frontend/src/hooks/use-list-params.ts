import { useCallback } from 'react'
import { useSearchParams } from 'react-router'

import type { ListParams } from '@/api/types'

const PAGE_PARAM = 'page'
const SEARCH_PARAM = 'search'
const FIRST_PAGE = 1

function parsePage(value: string | null) {
  const page = Number(value)
  return Number.isInteger(page) && page >= FIRST_PAGE ? page : FIRST_PAGE
}

/**
 * A list page's `?page=` and `?search=`, kept in the URL so the current view
 * survives a reload and can be shared or navigated back to. A new search
 * starts again from the first page.
 */
export function useListParams() {
  const [searchParams, setSearchParams] = useSearchParams()
  const params: ListParams = {
    page: parsePage(searchParams.get(PAGE_PARAM)),
    search: searchParams.get(SEARCH_PARAM) ?? '',
  }

  const setPage = useCallback(
    (page: number) =>
      setSearchParams((current) => {
        const next = new URLSearchParams(current)
        if (page > FIRST_PAGE) {
          next.set(PAGE_PARAM, String(page))
        } else {
          next.delete(PAGE_PARAM)
        }
        return next
      }),
    [setSearchParams],
  )

  const setSearch = useCallback(
    (search: string) =>
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current)
          next.delete(PAGE_PARAM)
          if (search) {
            next.set(SEARCH_PARAM, search)
          } else {
            next.delete(SEARCH_PARAM)
          }
          return next
        },
        // Typing shouldn't leave one history entry per keystroke.
        { replace: true },
      ),
    [setSearchParams],
  )

  return { ...params, setPage, setSearch }
}
