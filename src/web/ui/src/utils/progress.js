export function computeProgressPercent(watched, total) {
  if (total <= 0) {
    return 0
  }
  return Math.round((watched / total) * 100)
}

export function formatProgressFraction(watched, total) {
  if (total <= 0) {
    return `${watched}/?`
  }
  return `${watched}/${total}`
}

export function formatHoursMinutes(value, approximate = false) {
  const minutes = Number(value || 0)
  if (!Number.isFinite(minutes) || minutes <= 0) {
    return '0m'
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

  const parts = []
  if (years > 0) {
    parts.push(`${years}y`)
  }
  if (years > 0 || days > 0) {
    parts.push(`${days}d`)
  }
  if (years > 0 || days > 0 || hours > 0) {
    parts.push(`${hours}h`)
  }
  parts.push(`${remainder}m`)

  const compact = parts.join(' ')
  return approximate ? `~${compact}` : compact
}
