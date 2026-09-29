import type { Location } from 'react-router'

import { PATHS } from '@/app/paths'

/** Router state that remembers where a signed-out visitor was headed. */
export function returnState(location: Location) {
  return { from: `${location.pathname}${location.search}` }
}

export function getReturnPath(state: unknown) {
  if (state && typeof state === 'object' && 'from' in state && typeof state.from === 'string') {
    return state.from
  }
  return PATHS.home
}
