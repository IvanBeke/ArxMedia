import { computed, ref } from 'vue'
import { trackingAPI } from '@/api'
import { getApiErrorMessage } from '@/utils/errors'
import { canRateByStatus } from '@/utils/mediaStatus'
import type { MediaType } from '@/types/api'

/**
 * Star rating for detail pages. `getStatus` reads the current user status
 * (rating is only allowed once watched/watching); the view assigns
 * `userRating` from its own ratings load.
 */
export function useUserRating(options: {
  mediaType: MediaType
  getId: () => string | number
  getStatus: () => unknown
  getRateErrorMessage: () => string
  getRatedMessage: (score: number) => string
  notifySuccess: (message: string) => void
  notifyError: (message: string) => void
}) {
  const userRating = ref(0)
  const canRate = computed(() => canRateByStatus(options.getStatus()))

  async function submitRating(score: number) {
    try {
      await trackingAPI.rate({ media_type: options.mediaType, tmdb_id: options.getId(), score })
      options.notifySuccess(options.getRatedMessage(score))
    } catch (error) {
      options.notifyError(getApiErrorMessage(error, options.getRateErrorMessage()))
    }
  }

  return { userRating, canRate, submitRating }
}
