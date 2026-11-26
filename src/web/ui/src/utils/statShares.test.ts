import { describe, expect, it } from 'vitest'
import { toSlices } from '@/utils/statShares'

const item = (key: string, value: number) => ({ key, label: key.toUpperCase(), value, colorClass: 'text-blue-500' })

describe('toSlices', () => {
  it('gives each slice its share and where it starts', () => {
    const slices = toSlices([item('a', 3), item('b', 1)])

    expect(slices.map((slice) => [slice.share, slice.offset, slice.percent])).toEqual([[75, 0, 75], [25, 75, 25]])
  })

  it('keeps the rounded percentages adding up to 100', () => {
    const percents = toSlices([item('a', 1), item('b', 1), item('c', 1)]).map((slice) => slice.percent)

    expect(percents.reduce((sum, value) => sum + value, 0)).toBe(100)
    expect(percents).toEqual([34, 33, 33])
  })

  it('leaves the shares at zero when nothing is counted', () => {
    const slices = toSlices([item('a', 0), item('b', 0)])

    expect(slices.map((slice) => [slice.share, slice.percent])).toEqual([[0, 0], [0, 0]])
  })

  it('keeps the other fields of the input', () => {
    const [slice] = toSlices([{ ...item('a', 2), display: '2m' }])

    expect(slice).toMatchObject({ key: 'a', label: 'A', colorClass: 'text-blue-500', display: '2m' })
  })
})
