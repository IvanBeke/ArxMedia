import { describe, expect, it, vi } from 'vitest'

vi.mock('@/api', () => ({
  trackingAPI: { rate: vi.fn().mockResolvedValue({}) },
}))

import { trackingAPI as importedTrackingAPI } from '@/api'
import { MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { useUserRating } from '@/composables/useUserRating'

const trackingAPI = vi.mocked(importedTrackingAPI)

function setup(status: unknown = WATCH_ENTRY_STATUS.WATCHED) {
  const success: string[] = []
  const errors: string[] = []
  const rating = useUserRating({
    mediaType: MEDIA_TYPE.MOVIE,
    getId: () => 603,
    getStatus: () => status,
    getRateErrorMessage: () => 'Rate after watching.',
    getRatedMessage: (score) => `Rated ${score}/10!`,
    notifySuccess: (message) => success.push(message),
    notifyError: (message) => errors.push(message),
  })
  return { rating, success, errors }
}

describe('useUserRating', () => {
  it('rates only when the status allows it', () => {
    expect(setup(WATCH_ENTRY_STATUS.WATCHED).rating.canRate.value).toBe(true)
    expect(setup(WATCH_ENTRY_STATUS.WATCHING).rating.canRate.value).toBe(true)
    expect(setup('plan_to_watch').rating.canRate.value).toBe(false)
    expect(setup(null).rating.canRate.value).toBe(false)
  })

  it('submits the score and notifies success', async () => {
    const { rating, success, errors } = setup()

    await rating.submitRating(8)

    expect(trackingAPI.rate).toHaveBeenCalledWith({ media_type: 'movie', tmdb_id: 603, score: 8 })
    expect(success).toEqual(['Rated 8/10!'])
    expect(errors).toEqual([])
  })

  it('notifies the backend error message on failure', async () => {
    trackingAPI.rate.mockRejectedValueOnce({ detail: 'Too early.', status: 400 })
    const { rating, success, errors } = setup()

    await rating.submitRating(4)

    expect(success).toEqual([])
    expect(errors).toEqual(['Too early.'])
  })
})
