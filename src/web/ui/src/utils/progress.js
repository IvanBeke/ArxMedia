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
  const hours = Math.floor(minutes / 60)
  const remainder = minutes % 60
  const compact = hours > 0 ? `${hours}h ${remainder}m` : `${remainder}m`
  return approximate ? `~${compact}` : compact
}
