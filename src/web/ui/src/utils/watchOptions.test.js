import { beforeAll, describe, expect, it } from 'vitest'
import { Temporal as TemporalPolyfill, toTemporalInstant } from '@js-temporal/polyfill'
import { EPOCH_START_ISO } from '@/utils/temporal'
import { resolveWatchedAtFromOption } from '@/utils/watchOptions'

beforeAll(() => {
  if (!globalThis.Temporal) {
    globalThis.Temporal = TemporalPolyfill
  }
  if (!Date.prototype.toTemporalInstant) {
    Date.prototype.toTemporalInstant = toTemporalInstant
  }
})

describe('resolveWatchedAtFromOption', () => {
  it('marks now with no timestamp and no release flag', async () => {
    await expect(resolveWatchedAtFromOption('now')).resolves.toEqual({
      cancelled: false,
      watchedAt: null,
      useReleaseDate: false,
    })
  })

  it('converts a release date into a user instant', async () => {
    const result = await resolveWatchedAtFromOption('release', { releaseDate: '2020-05-01' })
    expect(result.cancelled).toBe(false)
    expect(result.useReleaseDate).toBe(true)
    expect(result.watchedAt).toBe('2020-05-01T00:00:00Z')
  })

  it('keeps a null timestamp when the item has no release date', async () => {
    const result = await resolveWatchedAtFromOption('release', { releaseDate: '' })
    expect(result.cancelled).toBe(false)
    expect(result.useReleaseDate).toBe(true)
    expect(result.watchedAt).toBeNull()
  })

  it('uses the epoch start sentinel for unknown date', async () => {
    const result = await resolveWatchedAtFromOption('unknown')
    expect(result.cancelled).toBe(false)
    expect(result.useReleaseDate).toBe(false)
    expect(result.watchedAt).toBe(EPOCH_START_ISO)
    expect(result.watchedAt).toBe('1970-01-01T00:00:00Z')
  })

  it('returns the picked value for the date option', async () => {
    const picked = '2024-01-02T03:04:05Z'
    const result = await resolveWatchedAtFromOption('date', {
      pickDateTime: async () => picked,
    })
    expect(result.cancelled).toBe(false)
    expect(result.watchedAt).toBe(picked)
  })

  it('reports cancellation when the picker is dismissed', async () => {
    const result = await resolveWatchedAtFromOption('date', {
      pickDateTime: async () => null,
    })
    expect(result.cancelled).toBe(true)
    expect(result.watchedAt).toBeNull()
  })

  it('reports cancellation when no picker was provided', async () => {
    const result = await resolveWatchedAtFromOption('date')
    expect(result.cancelled).toBe(true)
  })

  it('treats any other option like now', async () => {
    await expect(resolveWatchedAtFromOption('something-else')).resolves.toEqual({
      cancelled: false,
      watchedAt: null,
      useReleaseDate: false,
    })
  })
})
