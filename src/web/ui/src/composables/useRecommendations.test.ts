import { describe, expect, it, vi } from 'vitest'
import { MEDIA_TYPE } from '@/constants/tracking'
import { useRecommendations } from '@/composables/useRecommendations'

describe('useRecommendations', () => {
  it('stamps fetched items with the media type', async () => {
    const fetcher = vi.fn().mockResolvedValue({ results: [{ id: 1 }, { id: 2 }], page: 1, total_pages: 1, total_results: 2 })
    const { recommendations, loadingRecs, recsError, loadRecommendations } = useRecommendations(fetcher, MEDIA_TYPE.MOVIE, () => 603)

    const pending = loadRecommendations()
    expect(loadingRecs.value).toBe(true)
    await pending

    expect(fetcher).toHaveBeenCalledWith(603)
    expect(recommendations.value).toEqual([
      { id: 1, media_type: 'movie' },
      { id: 2, media_type: 'movie' },
    ])
    expect(loadingRecs.value).toBe(false)
    expect(recsError.value).toBe(false)
  })

  it('flags errors and keeps previous items', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('boom'))
    const { recommendations, recsError, loadRecommendations } = useRecommendations(fetcher, MEDIA_TYPE.TV, () => 1399)

    await loadRecommendations()

    expect(recsError.value).toBe(true)
    expect(recommendations.value).toEqual([])
  })

  it('applies status changes to the loaded items', async () => {
    const fetcher = vi.fn().mockResolvedValue({ results: [{ id: 1, user_status: { status: 'none' } }], page: 1, total_pages: 1, total_results: 1 })
    const { recommendations, loadRecommendations, handleRecommendationStatusChanged } = useRecommendations(fetcher, MEDIA_TYPE.MOVIE, () => 603)
    await loadRecommendations()

    handleRecommendationStatusChanged({ media_type: 'movie', tmdb_id: 1, status: 'watching' } as never)

    expect(recommendations.value[0]?.user_status).toMatchObject({ status: 'watching' })
  })
})
