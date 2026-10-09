import { trackingAPI } from '@/api'
import { MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { createTransientIdState, type MediaId } from '@/composables/useTransientIdState'
import type { MediaType } from '@/types/api'
import type { WatchEntryStatus } from '@/types/tracking'

const { isLoading, isPulsing, resetTransientState, triggerPulse, runWithLoading } = createTransientIdState()

export function useWatchedQuickActions() {
  /** Returns the new status and the watch moment the backend stored (it resolves tokens like "release_date"). */
  async function markWatched(
    mediaType: MediaType,
    tmdbId: MediaId,
    watchedAt: string | null = null,
  ): Promise<{ status: WatchEntryStatus; watchedAt: string | null } | null> {
    return runWithLoading(mediaType, tmdbId, async (id) => {
      if (mediaType === MEDIA_TYPE.TV) {
        const response = await trackingAPI.markEpisodeWatched({
          tmdb_id: id,
          season_number: 1,
          episode_number: 1,
          watched_at: watchedAt,
        })
        triggerPulse(mediaType, id)
        return { status: WATCH_ENTRY_STATUS.WATCHING, watchedAt: response.watched_at }
      }

      const entry = await trackingAPI.addToHistory({
        media_type: MEDIA_TYPE.MOVIE,
        tmdb_id: id,
        watched_at: watchedAt,
      })
      triggerPulse(mediaType, id)
      return { status: WATCH_ENTRY_STATUS.WATCHED, watchedAt: entry.watched_at }
    })
  }

  async function unmarkWatched(mediaType: MediaType, tmdbId: MediaId): Promise<boolean | null> {
    return runWithLoading(mediaType, tmdbId, async (id) => {
      if (mediaType === MEDIA_TYPE.TV) {
        await trackingAPI.unmarkShowWatched({ tmdb_id: id })
      } else {
        await trackingAPI.removeFromHistory({
          media_type: MEDIA_TYPE.MOVIE,
          tmdb_id: id,
        })
      }
      return true
    })
  }

  return {
    resetTransientState,
    isLoading,
    isPulsing,
    markWatched,
    unmarkWatched,
  }
}
