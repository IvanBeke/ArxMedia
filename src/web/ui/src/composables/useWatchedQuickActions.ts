import { ref, type Ref } from 'vue'
import { trackingAPI } from '@/api'
import { MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import type { MediaType } from '@/types/api'
import type { WatchEntryStatus } from '@/types/tracking'

type MediaId = string | number
type IdSetRef = Ref<Set<number>>

const loadingMovieIds = ref<Set<number>>(new Set())
const loadingTvIds = ref<Set<number>>(new Set())
const pulseMovieIds = ref<Set<number>>(new Set())
const pulseTvIds = ref<Set<number>>(new Set())

function getLoadingSet(mediaType: MediaType): IdSetRef {
  return mediaType === MEDIA_TYPE.TV ? loadingTvIds : loadingMovieIds
}

function getPulseSet(mediaType: MediaType): IdSetRef {
  return mediaType === MEDIA_TYPE.TV ? pulseTvIds : pulseMovieIds
}

function updateSet(targetRef: IdSetRef, id: number, include: boolean) {
  const next = new Set(targetRef.value)
  if (include) {
    next.add(id)
  } else {
    next.delete(id)
  }
  targetRef.value = next
}

export function useWatchedQuickActions() {
  function resetTransientState() {
    loadingMovieIds.value = new Set()
    loadingTvIds.value = new Set()
    pulseMovieIds.value = new Set()
    pulseTvIds.value = new Set()
  }

  function triggerPulse(mediaType: MediaType, tmdbId: MediaId) {
    const id = Number(tmdbId)
    const pulseSet = getPulseSet(mediaType)
    updateSet(pulseSet, id, true)
    setTimeout(() => {
      updateSet(pulseSet, id, false)
    }, 500)
  }

  function isLoading(mediaType: MediaType, tmdbId: MediaId) {
    return getLoadingSet(mediaType).value.has(Number(tmdbId))
  }

  function isPulsing(mediaType: MediaType, tmdbId: MediaId) {
    return getPulseSet(mediaType).value.has(Number(tmdbId))
  }

  async function markWatched(mediaType: MediaType, tmdbId: MediaId, watchedAt: string | null = null): Promise<WatchEntryStatus | null> {
    const id = Number(tmdbId)
    const loadingSet = getLoadingSet(mediaType)
    if (loadingSet.value.has(id)) {
      return null
    }

    updateSet(loadingSet, id, true)
    try {
      if (mediaType === MEDIA_TYPE.TV) {
        await trackingAPI.markEpisodeWatched({
          tmdb_id: id,
          season_number: 1,
          episode_number: 1,
          watched_at: watchedAt,
        })
        triggerPulse(mediaType, id)
        return WATCH_ENTRY_STATUS.WATCHING
      }

      await trackingAPI.addToHistory({
        media_type: MEDIA_TYPE.MOVIE,
        tmdb_id: id,
        watched_at: watchedAt,
      })
      triggerPulse(mediaType, id)
      return WATCH_ENTRY_STATUS.WATCHED
    } finally {
      updateSet(loadingSet, id, false)
    }
  }

  async function unmarkWatched(mediaType: MediaType, tmdbId: MediaId): Promise<boolean | null> {
    const id = Number(tmdbId)
    const loadingSet = getLoadingSet(mediaType)
    if (loadingSet.value.has(id)) {
      return null
    }

    updateSet(loadingSet, id, true)
    try {
      if (mediaType === MEDIA_TYPE.TV) {
        await trackingAPI.unmarkShowWatched({ tmdb_id: id })
      } else {
        await trackingAPI.removeFromHistory({
          media_type: MEDIA_TYPE.MOVIE,
          tmdb_id: id,
        })
      }
      return true
    } finally {
      updateSet(loadingSet, id, false)
    }
  }

  return {
    resetTransientState,
    isLoading,
    isPulsing,
    markWatched,
    unmarkWatched,
  }
}
