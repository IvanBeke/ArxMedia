import { ref, type Ref } from 'vue'
import { MEDIA_TYPE } from '@/constants/tracking'
import type { MediaType } from '@/types/api'

export type MediaId = string | number
type IdSetRef = Ref<Set<number>>

/**
 * Per-media-type loading/pulse id sets shared by quick actions.
 * Call once per module: every card showing the same item must observe
 * the same loading state, so instances must share these sets.
 */
export function createTransientIdState(pulseMs = 500) {
  const loadingMovieIds = ref<Set<number>>(new Set())
  const loadingTvIds = ref<Set<number>>(new Set())
  const pulseMovieIds = ref<Set<number>>(new Set())
  const pulseTvIds = ref<Set<number>>(new Set())
  const pulseTimers = new Map<string, ReturnType<typeof setTimeout>>()

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

  function resetTransientState() {
    loadingMovieIds.value = new Set()
    loadingTvIds.value = new Set()
    pulseMovieIds.value = new Set()
    pulseTvIds.value = new Set()
    for (const timer of pulseTimers.values()) clearTimeout(timer)
    pulseTimers.clear()
  }

  function triggerPulse(mediaType: MediaType, tmdbId: MediaId) {
    const id = Number(tmdbId)
    const key = `${mediaType}:${id}`
    const existing = pulseTimers.get(key)
    if (existing !== undefined) clearTimeout(existing)
    updateSet(getPulseSet(mediaType), id, true)
    pulseTimers.set(key, setTimeout(() => {
      pulseTimers.delete(key)
      updateSet(getPulseSet(mediaType), id, false)
    }, pulseMs))
  }

  function isLoading(mediaType: MediaType, tmdbId: MediaId) {
    return getLoadingSet(mediaType).value.has(Number(tmdbId))
  }

  function isPulsing(mediaType: MediaType, tmdbId: MediaId) {
    return getPulseSet(mediaType).value.has(Number(tmdbId))
  }

  /** Runs `fn` under the item's loading flag; returns null when already busy. */
  async function runWithLoading<T>(mediaType: MediaType, tmdbId: MediaId, fn: (id: number) => Promise<T>): Promise<T | null> {
    const id = Number(tmdbId)
    const loadingSet = getLoadingSet(mediaType)
    if (loadingSet.value.has(id)) return null
    updateSet(loadingSet, id, true)
    try {
      return await fn(id)
    } finally {
      updateSet(loadingSet, id, false)
    }
  }

  return { isLoading, isPulsing, resetTransientState, triggerPulse, runWithLoading }
}
