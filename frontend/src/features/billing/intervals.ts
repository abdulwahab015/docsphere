/** Stripe's recurring intervals, as a plan's title ("Monthly plan") and as
 * the per-period part of a price ("€15 per month"). */
export const INTERVAL_TITLES: Record<string, string> = {
  day: 'Daily',
  week: 'Weekly',
  month: 'Monthly',
  year: 'Yearly',
}

export const INTERVAL_PERIODS: Record<string, string> = {
  day: 'per day',
  week: 'per week',
  month: 'per month',
  year: 'per year',
}
