export function adjacentCalendarDay(day: string, direction: -1 | 1): string | null {
  const date = new Date(day + 'T12:00:00')
  if (Number.isNaN(date.getTime())) return null
  date.setDate(date.getDate() + direction)
  const year = date.getFullYear()
  if (year < 1 || year > 9998) return null
  return [String(year).padStart(4, '0'), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-')
}
