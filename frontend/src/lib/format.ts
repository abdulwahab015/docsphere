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

const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})

/** An API timestamp as a date and time, e.g. when something was last saved. */
export function formatDateTime(isoTimestamp: string) {
  return dateTimeFormat.format(new Date(isoTimestamp))
}

/** An amount in a currency's smallest unit - as Stripe reports prices, e.g.
 * cents - in the viewer's locale. Zero-decimal currencies (yen) need no
 * conversion; the currency's own number of decimals decides. */
export function formatMoney(minorUnits: number, currency: string) {
  const format = new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: currency.toUpperCase(),
  })
  const decimals = format.resolvedOptions().maximumFractionDigits ?? 0
  return format.format(minorUnits / 10 ** decimals)
}
