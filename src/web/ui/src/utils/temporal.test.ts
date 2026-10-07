import { describe, expect, it } from 'vitest'
import {
  formatIsoAsDDMMYYYY,
  formatIsoTimeHHMM,
  formatTemporalDateTime,
  isoDateKey,
  localDateTimeInputToIso,
  toLocalDateTimeInput,
  weekBounds,
} from './temporal'

describe('temporal utils', () => {
  it('keeps plain date key stable for date-only values', () => {
    expect(isoDateKey('2026-02-03')).toBe('2026-02-03')
  })

  it('returns valid local input and round-trips back to iso instant', () => {
    const iso = '2026-08-19T14:45:00Z'
    const localInput = toLocalDateTimeInput(iso, 'UTC')
    expect(localInput).toBe('2026-08-19T14:45')
    expect(localDateTimeInputToIso(localInput, 'UTC')).toBe('2026-08-19T14:45:00Z')
  })

  it('formats date and time labels from ISO', () => {
    const iso = '2026-08-19T09:07:00Z'
    expect(formatIsoAsDDMMYYYY(iso)).toMatch(/^\d{2}\/\d{2}\/\d{4}$/)
    expect(formatIsoTimeHHMM(iso, 'UTC')).toBe('09:07')
  })

  it('formats localized date times using a 24-hour clock', () => {
    const formatted = formatTemporalDateTime(
      '2026-08-19T13:07:00Z',
      'en-US',
      { month: 'long', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false },
    )

    expect(formatted).toContain('13:07')
    expect(formatted).not.toMatch(/\b(?:AM|PM)\b/)
  })

  it('returns monday-to-sunday bounds for week containing value', () => {
    const midWeek = weekBounds('2026-08-19')
    expect(midWeek?.start.toString()).toBe('2026-08-17')
    expect(midWeek?.end.toString()).toBe('2026-08-23')

    const sunday = weekBounds('2026-08-23')
    expect(sunday?.start.toString()).toBe('2026-08-17')
    expect(sunday?.end.toString()).toBe('2026-08-23')

    const yearBoundary = weekBounds('2027-01-01')
    expect(yearBoundary?.start.toString()).toBe('2026-12-28')
    expect(yearBoundary?.end.toString()).toBe('2027-01-03')

    expect(weekBounds('not-a-date')).toBeNull()
  })
})
