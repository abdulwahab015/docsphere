import { useParams } from 'react-router'

/** A numeric id from the URL (e.g. `:projectId`), or `undefined` when the
 * segment isn't a positive whole number - so a malformed link shows "not
 * found" without a pointless request. */
export function useIdParam(name: string) {
  const id = Number(useParams()[name])
  return Number.isInteger(id) && id > 0 ? id : undefined
}
