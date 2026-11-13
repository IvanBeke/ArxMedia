import type { MessageKey } from '@/i18n'

export function computeProgressPercent(watched: number, total: number): number {
  if (total <= 0) {
    return 0
  }
  return Math.round((watched / total) * 100)
}

export function formatProgressFraction(watched: number, total: number): string {
  if (total <= 0) {
    return `${watched}/?`
  }
  return `${watched}/${total}`
}

export function formatHoursMinutes(value: unknown, approximate = false, t?: (key: MessageKey) => string): string {
  const yearUnit = t ? t('format_unit_year') : 'y'
  const minuteUnit = t ? t('format_unit_minute') : 'm'
  const minutes = Number(value || 0)
  if (!Number.isFinite(minutes) || minutes <= 0) {
    return `0${minuteUnit}`
  }
  const MINUTES_PER_HOUR = 60
  const MINUTES_PER_DAY = 24 * MINUTES_PER_HOUR
  const MINUTES_PER_YEAR = 365 * MINUTES_PER_DAY

  let remaining = Math.floor(minutes)
  const years = Math.floor(remaining / MINUTES_PER_YEAR)
  remaining %= MINUTES_PER_YEAR
  const days = Math.floor(remaining / MINUTES_PER_DAY)
  remaining %= MINUTES_PER_DAY
  const hours = Math.floor(remaining / MINUTES_PER_HOUR)
  const remainder = remaining % MINUTES_PER_HOUR

  const parts: string[] = []
  if (years > 0) {
    parts.push(`${years}${yearUnit}`)
  }
  if (years > 0 || days > 0) {
    parts.push(`${days}d`)
  }
  if (years > 0 || days > 0 || hours > 0) {
    parts.push(`${hours}h`)
  }
  parts.push(`${remainder}${minuteUnit}`)

  const compact = parts.join(' ')
  return approximate ? `~${compact}` : compact
}
