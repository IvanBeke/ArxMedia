import { beforeAll, describe, expect, it } from 'vitest'
import { Temporal as TemporalPolyfill, toTemporalInstant } from '@js-temporal/polyfill'
import {
  formatIsoAsDDMMYYYY,
  formatIsoTimeHHMM,
  isoDateKey,
  localDateTimeInputToIso,
  plainDateToUserInstantIso,
  toLocalDateTimeInput,
} from './temporal'

beforeAll(() => {
  if (!globalThis.Temporal) {
    globalThis.Temporal = TemporalPolyfill
  }
  if (!Date.prototype.toTemporalInstant) {
    Date.prototype.toTemporalInstant = toTemporalInstant
  }
})

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

  it('converts plain date to midnight instant for selected timezone', () => {
    expect(plainDateToUserInstantIso('2026-03-10', 'UTC')).toBe('2026-03-10T00:00:00Z')
    expect(plainDateToUserInstantIso('not-a-date', 'UTC')).toBe('')
  })
})
