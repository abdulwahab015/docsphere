const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })
const longDateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'long' })

/** An API timestamp (ISO 8601) as a short date in the viewer's locale. */
export function formatDate(isoTimestamp: string) {
  return dateFormat.format(new Date(isoTimestamp))
}

/** An API timestamp as a spelled-out date, e.g. for billing dates. */
export function formatLongDate(isoTimestamp: string) {
  return longDateFormat.format(new Date(isoTimestamp))
}
