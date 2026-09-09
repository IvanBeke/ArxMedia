import { ref, type Ref } from 'vue'
import { trackingAPI } from '@/api'
import { MEDIA_TYPE } from '@/constants/tracking'
import type { MediaCard, MediaType } from '@/types/api'

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

export function useWatchlistQuickActions() {
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

  async function getWatchlistItem(mediaType: MediaType, tmdbId: MediaId): Promise<MediaCard | null> {
    const data = await trackingAPI.getWatchlist({ media_type: mediaType, tmdb_id: tmdbId })
    const entries = data?.results || data || []
    return entries[0] || null
  }

  function isLoading(mediaType: MediaType, tmdbId: MediaId) {
    return getLoadingSet(mediaType).value.has(Number(tmdbId))
  }

  function isPulsing(mediaType: MediaType, tmdbId: MediaId) {
    return getPulseSet(mediaType).value.has(Number(tmdbId))
  }

  async function addToWatchlist(mediaType: MediaType, tmdbId: MediaId) {
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

  async function removeFromWatchlist(mediaType: MediaType, tmdbId: MediaId) {
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
