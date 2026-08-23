import { beforeAll, describe, expect, it, vi } from 'vitest'
import { Temporal as TemporalPolyfill, toTemporalInstant } from '@js-temporal/polyfill'

vi.mock('@/api', () => ({
  trackingAPI: {
    markEpisodeWatched: vi.fn().mockResolvedValue({}),
    unmarkEpisodeWatched: vi.fn().mockResolvedValue({}),
  },
}))

import { trackingAPI } from '@/api'
import { useEpisodeWatchActions } from '@/composables/useEpisodeWatchActions'
import { EPOCH_START_ISO } from '@/utils/temporal'

beforeAll(() => {
  if (!globalThis.Temporal) {
    globalThis.Temporal = TemporalPolyfill
  }
  if (!Date.prototype.toTemporalInstant) {
    Date.prototype.toTemporalInstant = toTemporalInstant
  }
})

const TARGET = { tmdbId: 37854, seasonNumber: 2, episodeNumber: 5 }

describe('useEpisodeWatchActions', () => {
  it('marks watched now with a null timestamp and returns the current instant', async () => {
    trackingAPI.markEpisodeWatched.mockClear()
    const { markFromOption } = useEpisodeWatchActions()

    const result = await markFromOption('now', TARGET)

    expect(trackingAPI.markEpisodeWatched).toHaveBeenCalledWith({
      tmdb_id: 37854,
      season_number: 2,
      episode_number: 5,
      watched_at: null,
    })
    expect(result).toBeTruthy()
  })

  it('sends the epoch start sentinel for the unknown option', async () => {
    trackingAPI.markEpisodeWatched.mockClear()
    const { markFromOption } = useEpisodeWatchActions()

    const result = await markFromOption('unknown', TARGET)

    expect(trackingAPI.markEpisodeWatched).toHaveBeenCalledWith(
      expect.objectContaining({ watched_at: EPOCH_START_ISO })
    )
    expect(result).toBe(EPOCH_START_ISO)
  })

  it('converts the release date before marking', async () => {
    trackingAPI.markEpisodeWatched.mockClear()
    const { markFromOption } = useEpisodeWatchActions()

    await markFromOption('release', TARGET, { releaseDate: '2020-05-01' })

    expect(trackingAPI.markEpisodeWatched).toHaveBeenCalledWith(
      expect.objectContaining({ watched_at: '2020-05-01T00:00:00Z' })
    )
  })

  it('aborts without calling the API when the picker is dismissed', async () => {
    trackingAPI.markEpisodeWatched.mockClear()
    const { markFromOption, showDatePicker, handleDatePickerCancel } = useEpisodeWatchActions()

    const pending = markFromOption('date', TARGET)
    handleDatePickerCancel()
    const result = await pending

    expect(showDatePicker.value).toBe(false)
    expect(result).toBeNull()
    expect(trackingAPI.markEpisodeWatched).not.toHaveBeenCalled()
  })

  it('reports API failures through onError and returns null', async () => {
    trackingAPI.unmarkEpisodeWatched.mockRejectedValueOnce(new Error('boom'))
    const errors = []
    const { unmark } = useEpisodeWatchActions({ onError: (message) => errors.push(message) })

    const result = await unmark(TARGET)

    expect(result).toBe(false)
    expect(errors).toHaveLength(1)
    expect(errors[0]).toContain('Could not unmark')
  })
})
