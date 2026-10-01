import { useCallback } from 'react'
import { useSearchParams } from 'react-router'

const TAB_PARAM = 'tab'

/**
 * The open tab of a tabbed page, kept in `?tab=` so a reload or a shared link
 * opens the same one; the first tab is the default and leaves the URL clean.
 * Switching tabs drops the other list params (`?page=`, `?search=`), so each
 * tab starts on its own first page. `tabs` should be a module-level constant.
 */
export function useTabParam<Tab extends string>(tabs: readonly [Tab, ...Tab[]]) {
  const [searchParams, setSearchParams] = useSearchParams()
  const requested = searchParams.get(TAB_PARAM)
  const tab = tabs.find((candidate) => candidate === requested) ?? tabs[0]

  const setTab = useCallback(
    (nextTab: string) => setSearchParams(nextTab === tabs[0] ? {} : { [TAB_PARAM]: nextTab }),
    [setSearchParams, tabs],
  )

  return [tab, setTab] as const
}
