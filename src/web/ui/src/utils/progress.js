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
