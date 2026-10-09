import { trackingAPI } from '@/api'
import { createTransientIdState, type MediaId } from '@/composables/useTransientIdState'
import type { MediaCard, MediaType } from '@/types/api'

const { isLoading, isPulsing, resetTransientState, triggerPulse, runWithLoading } = createTransientIdState()

export function useWatchlistQuickActions() {
  async function getWatchlistItem(mediaType: MediaType, tmdbId: MediaId): Promise<MediaCard | null> {
    const data = await trackingAPI.getWatchlist({ media_type: mediaType, tmdb_id: tmdbId })
    const entries = data?.results || data || []
    return entries[0] || null
  }

  async function addToWatchlist(mediaType: MediaType, tmdbId: MediaId) {
    await runWithLoading(mediaType, tmdbId, async (id) => {
      await trackingAPI.addToWatchlist({ media_type: mediaType, tmdb_id: id })
      triggerPulse(mediaType, id)
    })
  }

  async function removeFromWatchlist(mediaType: MediaType, tmdbId: MediaId) {
    await runWithLoading(mediaType, tmdbId, async (id) => {
      const watchlistItem = await getWatchlistItem(mediaType, id)
      if (!watchlistItem?.id) {
        return
      }
      await trackingAPI.removeFromWatchlist(watchlistItem.id)
    })
  }

  async function toggleWatchlist(mediaType: MediaType, tmdbId: MediaId, isInWatchlist: boolean): Promise<'removed' | 'added'> {
    if (isInWatchlist) {
      await removeFromWatchlist(mediaType, tmdbId)
      return 'removed'
    }
    await addToWatchlist(mediaType, tmdbId)
    return 'added'
  }

  return {
    resetTransientState,
    isLoading,
    isPulsing,
    addToWatchlist,
    removeFromWatchlist,
    toggleWatchlist,
  }
}
