import { ref } from 'vue'
import { trackingAPI } from '@/api'
import { MEDIA_TYPE } from '@/constants/tracking'

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

export function useWatchlistQuickActions() {
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

  async function getWatchlistItem(mediaType, tmdbId) {
    const data = await trackingAPI.getWatchlist({ media_type: mediaType, tmdb_id: tmdbId })
    const entries = data?.results || data || []
    return entries[0] || null
  }

  function isLoading(mediaType, tmdbId) {
    return getLoadingSet(mediaType).value.has(Number(tmdbId))
  }

  function isPulsing(mediaType, tmdbId) {
    return getPulseSet(mediaType).value.has(Number(tmdbId))
  }

  async function addToWatchlist(mediaType, tmdbId) {
    const id = Number(tmdbId)
    const loadingSet = getLoadingSet(mediaType)

    if (loadingSet.value.has(id)) {
      return
    }

    updateSet(loadingSet, id, true)
    try {
      await trackingAPI.addToWatchlist({ media_type: mediaType, tmdb_id: id })
      triggerPulse(mediaType, id)
    } finally {
      updateSet(loadingSet, id, false)
    }
  }

  async function removeFromWatchlist(mediaType, tmdbId) {
    const id = Number(tmdbId)
    const loadingSet = getLoadingSet(mediaType)

    if (loadingSet.value.has(id)) {
      return
    }

    updateSet(loadingSet, id, true)
    try {
      const watchlistItem = await getWatchlistItem(mediaType, id)
      if (!watchlistItem?.id) {
        return
      }
      await trackingAPI.removeFromWatchlist(watchlistItem.id)
    } finally {
      updateSet(loadingSet, id, false)
    }
  }

  async function toggleWatchlist(mediaType, tmdbId, isInWatchlist) {
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
