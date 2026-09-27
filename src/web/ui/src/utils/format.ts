export function formatRating(value: number | string | null | undefined, decimals = 1): string {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toFixed(decimals)
  }
  return String(value ?? '')
}
