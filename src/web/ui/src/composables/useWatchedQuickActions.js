import { ref } from 'vue'
import { trackingAPI } from '@/api'
import { MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'

const loadingMovieIds = ref(new Set())
const loadingTvIds = ref(new Set())
const pulseMovieIds = ref(new Set())
const pulseTvIds = ref(new Set())

function getLoadingSet(mediaType) {
  return mediaType === MEDIA_TYPE.TV ? loadingTvIds : loadingMovieIds
}

function getPulseSet(mediaType) {
  return mediaType === MEDIA_TYPE.TV ? pulseTvIds : pulseMovieIds
}

function updateSet(targetRef, id, include) {
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

  function triggerPulse(mediaType, tmdbId) {
    const id = Number(tmdbId)
    const pulseSet = getPulseSet(mediaType)
    updateSet(pulseSet, id, true)
    setTimeout(() => {
      updateSet(pulseSet, id, false)
    }, 500)
  }

  function isLoading(mediaType, tmdbId) {
    return getLoadingSet(mediaType).value.has(Number(tmdbId))
  }

  function isPulsing(mediaType, tmdbId) {
    return getPulseSet(mediaType).value.has(Number(tmdbId))
  }

  async function markWatched(mediaType, tmdbId, watchedAt = null) {
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

  return {
    resetTransientState,
    isLoading,
    isPulsing,
    markWatched,
  }
}
