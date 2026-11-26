import type { StatSlice, StatSliceInput } from '@/types/stats'

export function toSlices(items: StatSliceInput[]): StatSlice[] {
  const total = items.reduce((sum, item) => sum + item.value, 0)
  let offset = 0
  const slices = items.map((item) => {
    const share = total > 0 ? (item.value / total) * 100 : 0
    const slice = { ...item, share, offset, percent: Math.round(share) }
    offset += share
    return slice
  })
  // Rounded percentages can total 99 or 101; the largest slice absorbs the difference.
  const largest = [...slices].sort((a, b) => b.value - a.value)[0]
  if (total > 0 && largest) largest.percent += 100 - slices.reduce((sum, slice) => sum + slice.percent, 0)
  return slices
}
