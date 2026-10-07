import { describe, expect, it, vi } from 'vitest'

vi.mock('@/api', () => ({
  trackingAPI: {
    markEpisodeWatched: vi.fn().mockResolvedValue({ id: 1, created: true, watched_at: '2020-05-01T21:00:00Z' }),
    unmarkEpisodeWatched: vi.fn().mockResolvedValue({}),
  },
}))

import { trackingAPI as importedTrackingAPI } from '@/api'
import { useEpisodeWatchActions } from '@/composables/useEpisodeWatchActions'

const trackingAPI = vi.mocked(importedTrackingAPI)

const TARGET = { tmdbId: 37854, seasonNumber: 2, episodeNumber: 5 }

describe('useEpisodeWatchActions', () => {
  it.each([
    ['now', 'now'],
    ['unknown', 'unknown'],
    ['release', 'release_date'],
  ])('sends the %s option as the %s token and returns the moment the backend stored', async (option, token) => {
    trackingAPI.markEpisodeWatched.mockClear()
    const { markFromOption } = useEpisodeWatchActions()

    const result = await markFromOption(option, TARGET)

    expect(trackingAPI.markEpisodeWatched).toHaveBeenCalledWith({
      tmdb_id: 37854,
      season_number: 2,
      episode_number: 5,
      watched_at: token,
    })
    expect(result).toEqual({ watchedAt: '2020-05-01T21:00:00Z' })
  })

  it('treats an unknown watch date from the backend as a successful mark', async () => {
    trackingAPI.markEpisodeWatched.mockResolvedValueOnce({ id: 1, created: true, watched_at: null })
    const { markFromOption } = useEpisodeWatchActions()

    await expect(markFromOption('unknown', TARGET)).resolves.toEqual({ watchedAt: null })
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
    const errors: string[] = []
    const { unmark } = useEpisodeWatchActions({ onError: (message) => errors.push(message) })

    const result = await unmark(TARGET)

    expect(result).toBe(false)
    expect(errors).toHaveLength(1)
    expect(errors[0]).toContain('Could not unmark')
  })
})
