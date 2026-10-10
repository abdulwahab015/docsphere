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

const BYTES_PER_KILOBYTE = 1024
const SIZE_UNITS = ['KB', 'MB', 'GB'] as const

/** A file size the way a person reads it: "820 B", "12 KB", "3.4 MB". */
export function formatBytes(bytes: number) {
  if (bytes < BYTES_PER_KILOBYTE) {
    return `${bytes} B`
  }
  let size = bytes / BYTES_PER_KILOBYTE
  let unit = 0
  while (size >= BYTES_PER_KILOBYTE && unit < SIZE_UNITS.length - 1) {
    size /= BYTES_PER_KILOBYTE
    unit += 1
  }
  return `${size < 10 ? size.toFixed(1) : Math.round(size)} ${SIZE_UNITS[unit]}`
}
