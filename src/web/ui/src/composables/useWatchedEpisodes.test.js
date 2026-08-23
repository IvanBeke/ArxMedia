import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api', () => ({
  trackingAPI: {
    getWatchedEpisodes: vi.fn(),
  },
}))

import { trackingAPI } from '@/api'
import { useWatchedEpisodes } from '@/composables/useWatchedEpisodes'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useWatchedEpisodes', () => {
  it('uses composite season-episode keys for local mark and unmark', () => {
    const state = useWatchedEpisodes()

    expect(state.isWatched(2, 5)).toBe(false)

    state.markLocally(2, 5, '2024-01-02T03:04:05Z')
    expect(state.isWatched(2, 5)).toBe(true)
    expect(state.watchedAt(2, 5)).toBe('2024-01-02T03:04:05Z')
    expect(state.watchedEps.value.has('2-5')).toBe(true)
    // Same episode number in another season stays independent
    expect(state.isWatched(3, 5)).toBe(false)

    state.unmarkLocally(2, 5)
    expect(state.isWatched(2, 5)).toBe(false)
    expect(state.watchedAt(2, 5)).toBe('')
  })

  it('applies a full response replacing previous state', () => {
    const state = useWatchedEpisodes()
    state.markLocally(9, 9, '')

    state.applyResponse({
      episodes: [
        { season_number: 1, episode_number: 1, watched_at: '2020-01-01T00:00:00Z' },
        { season_number: 1, episode_number: 2, watched_at: null },
      ],
    })

    expect(state.isWatched(1, 1)).toBe(true)
    expect(state.watchedAt(1, 1)).toBe('2020-01-01T00:00:00Z')
    expect(state.isWatched(1, 2)).toBe(true)
    expect(state.watchedAt(1, 2)).toBe('')
    expect(state.isWatched(9, 9)).toBe(false)
  })

  it('filters by season when asked', () => {
    const state = useWatchedEpisodes()

    state.applyResponse(
      {
        episodes: [
          { season_number: 1, episode_number: 1, watched_at: null },
          { season_number: 2, episode_number: 3, watched_at: null },
        ],
      },
      { seasonNumber: 2 }
    )

    expect(state.isWatched(1, 1)).toBe(false)
    expect(state.isWatched(2, 3)).toBe(true)
  })

  it('loads through the API and reports failures via onError', async () => {
    const state = useWatchedEpisodes()

    trackingAPI.getWatchedEpisodes.mockResolvedValueOnce({
      episodes: [{ season_number: 4, episode_number: 7, watched_at: null }],
    })
    await state.load(99)
    expect(state.isWatched(4, 7)).toBe(true)

    const onError = vi.fn()
    trackingAPI.getWatchedEpisodes.mockRejectedValueOnce(new Error('boom'))
    const result = await state.load(99, { onError })
    expect(result).toBeNull()
    expect(onError).toHaveBeenCalledTimes(1)
  })
})
