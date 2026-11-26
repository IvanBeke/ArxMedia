import { describe, expect, it } from 'vitest'
import { messages, type MessageKey } from '@/i18n'
import {
  habitCharts,
  mediaTypeSlices,
  monthlyColumns,
  movieStatusSlices,
  ratingColumns,
  showStatusSlices,
  watchTimeSlices,
} from '@/utils/statsCharts'
import { habitsStats, libraryStats, monthlyStats, watchTimeStats } from '@/test-support/stats'

const t = (key: MessageKey) => messages.en[key]

describe('statsCharts', () => {
  it('lists show statuses in display order with the status badge colours', () => {
    const slices = showStatusSlices(libraryStats().show_statuses, t)

    expect(slices.map((slice) => [slice.key, slice.label, slice.value, slice.colorClass])).toEqual([
      ['watching', 'Watching', 2, 'text-brand-500'],
      ['watched', 'Watched', 3, 'text-emerald-600'],
      ['plan_to_watch', 'Plan to watch', 1, 'text-indigo-600'],
      ['dropped', 'Dropped', 0, 'text-rose-600'],
    ])
  })

  it('leaves "watching" out of the movie statuses', () => {
    expect(movieStatusSlices(libraryStats().movie_statuses, t).map((slice) => [slice.key, slice.value])).toEqual([
      ['watched', 10], ['plan_to_watch', 2], ['dropped', 1],
    ])
  })

  it('colours movies and shows consistently', () => {
    expect(mediaTypeSlices(libraryStats().media_types, t).map((slice) => [slice.label, slice.value, slice.colorClass])).toEqual([
      ['Movies', 13, 'text-blue-500'], ['Shows', 6, 'text-brand-500'],
    ])
    expect(watchTimeSlices(watchTimeStats(), t).map((slice) => [slice.label, slice.display, slice.colorClass])).toEqual([
      ['Movies', '1h 40m', 'text-blue-500'], ['Episodes', '50m', 'text-brand-500'],
    ])
  })

  it('numbers the rating columns from 1', () => {
    const columns = ratingColumns([0, 2, 5])

    expect(columns.map((column) => [column.key, column.label, column.value])).toEqual([['1', '1', 0], ['2', '2', 2], ['3', '3', 5]])
  })

  it('stacks each month with episodes at the bottom and describes it in the tooltip', () => {
    const [last] = monthlyColumns(monthlyStats().months, t, 'en-US').slice(-1)

    expect(last).toMatchObject({ key: '2026-12', label: 'Dec', value: 150, display: '3h' })
    expect(last!.title).toBe('December 2026: Movies 1h 40m · Episodes 50m')
    expect(last!.segments).toEqual([
      { value: 50, barClass: 'bg-brand-500' },
      { value: 100, barClass: 'bg-blue-500' },
    ])
  })

  it('builds the four habit charts, by-time ones on a full row', () => {
    const charts = habitCharts(habitsStats(), t, 'en-US')

    expect(charts.map((chart) => [chart.key, chart.fullRow, chart.barClass, chart.hasData])).toEqual([
      ['movies-day', false, 'bg-blue-500', true],
      ['episodes-day', false, 'bg-brand-500', true],
      ['movies-time', true, 'bg-blue-500', true],
      ['episodes-time', true, 'bg-brand-500', true],
    ])
    expect(charts[0]!.items.map((item) => item.label)).toEqual(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
    expect(charts[0]!.items[6]!.title).toBe('Sunday: 3')
    expect(charts[2]!.items).toHaveLength(24)
    expect(charts[2]!.items.slice(0, 2).map((item) => item.label)).toEqual(['00', '01'])
    expect(charts[2]!.items[21]!.title).toBe('21:00: 4')
  })

  it('names the weekdays in the given locale', () => {
    const [movies] = habitCharts(habitsStats(), t, 'es-ES')

    expect(movies!.items.map((item) => item.label)).toEqual(['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom'])
  })

  it('returns empty chart shells while there is no data', () => {
    const charts = habitCharts(null, t, 'en-US')

    expect(charts).toHaveLength(4)
    expect(charts.every((chart) => chart.items.length === 0 && !chart.hasData)).toBe(true)
  })
})
