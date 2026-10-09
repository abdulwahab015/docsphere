const DAY_PATTERN = /^\d{4}-\d{2}-\d{2}$/

/** Whether `value` is a day as a date input gives it (`YYYY-MM-DD`). */
export function isDay(value: string) {
  return DAY_PATTERN.test(value)
}

/** The moment `day` begins where the viewer is, as the API takes it. */
export function startOfDay(day: string) {
  return new Date(`${day}T00:00`).toISOString()
}

/** The moment `day` ends - the next one begins - where the viewer is. */
export function startOfNextDay(day: string) {
  const next = new Date(`${day}T00:00`)
  next.setDate(next.getDate() + 1)
  return next.toISOString()
}
