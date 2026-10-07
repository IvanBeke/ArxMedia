import { describe, expect, it } from 'vitest'
import { resolveWatchedAtFromOption } from '@/utils/watchOptions'

describe('resolveWatchedAtFromOption', () => {
  it.each([
    ['now', 'now'],
    ['release', 'release_date'],
    ['unknown', 'unknown'],
    ['something-else', 'now'],
  ])('maps the %s option to the %s token for the backend to resolve', async (option, token) => {
    await expect(resolveWatchedAtFromOption(option)).resolves.toEqual({ cancelled: false, watchedAt: token })
  })

  it('returns the picked timestamp for the date option', async () => {
    const picked = '2024-01-02T03:04:05Z'
    const result = await resolveWatchedAtFromOption('date', { pickDateTime: async () => picked })
    expect(result).toEqual({ cancelled: false, watchedAt: picked })
  })

  it('reports cancellation when the picker is dismissed or missing', async () => {
    await expect(resolveWatchedAtFromOption('date', { pickDateTime: async () => null })).resolves.toEqual({ cancelled: true, watchedAt: null })
    await expect(resolveWatchedAtFromOption('date')).resolves.toEqual({ cancelled: true, watchedAt: null })
  })
})
