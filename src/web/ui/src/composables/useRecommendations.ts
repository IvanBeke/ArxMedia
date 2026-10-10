import { ref } from 'vue'
import { applyStatusChanged, type MediaStatusChangedPayload } from '@/utils/mediaStatusSync'
import type { MediaResult, MediaSearchResponse, MediaType } from '@/types/api'

/**
 * "More like this" row for detail pages. `fetcher` loads a page of
 * recommendations for an id; every item is stamped with `mediaType`.
 */
export function useRecommendations(
  fetcher: (id: string | number) => Promise<MediaSearchResponse>,
  mediaType: MediaType,
  getId: () => string | number,
) {
  const recommendations = ref<MediaResult[]>([])
  const loadingRecs = ref(false)
  const recsError = ref(false)

  async function loadRecommendations() {
    loadingRecs.value = true
    recsError.value = false
    try {
      const data = await fetcher(getId())
      recommendations.value = (data.results || []).map((item) => ({ ...item, media_type: mediaType }))
    } catch {
      recsError.value = true
    } finally {
      loadingRecs.value = false
    }
  }

  function handleRecommendationStatusChanged(payload: MediaStatusChangedPayload) {
    applyStatusChanged(recommendations.value, payload)
  }

  return { recommendations, loadingRecs, recsError, loadRecommendations, handleRecommendationStatusChanged }
}
