import { ref } from 'vue'
import { trackingAPI } from '@/api'
import type { WatchedEpisode } from '@/types/api'

type WatchedEpisodesResponse = { episodes: WatchedEpisode[] }
type LoadOptions = { seasonNumber?: number | null; onError?: (error: unknown) => void }

export function episodeKey(seasonNumber: number, episodeNumber: number) {
  return `${seasonNumber}-${episodeNumber}`
}

export function useWatchedEpisodes() {
  const watchedEps = ref<Set<string>>(new Set())
  const watchedAtMap = ref<Map<string, string>>(new Map())

  function isWatched(seasonNumber: number, episodeNumber: number) {
    return watchedEps.value.has(episodeKey(seasonNumber, episodeNumber))
  }

  function watchedAt(seasonNumber: number, episodeNumber: number) {
    return watchedAtMap.value.get(episodeKey(seasonNumber, episodeNumber)) || ''
  }

  function markLocally(seasonNumber: number, episodeNumber: number, atIso: string | null) {
    watchedEps.value.add(episodeKey(seasonNumber, episodeNumber))
    watchedAtMap.value.set(episodeKey(seasonNumber, episodeNumber), atIso || '')
  }

  function unmarkLocally(seasonNumber: number, episodeNumber: number) {
    watchedEps.value.delete(episodeKey(seasonNumber, episodeNumber))
    watchedAtMap.value.delete(episodeKey(seasonNumber, episodeNumber))
  }

  function applyResponse(response: WatchedEpisodesResponse | null | undefined, { seasonNumber = null }: Pick<LoadOptions, 'seasonNumber'> = {}) {
    const episodes = response?.episodes ?? []
    const filtered = seasonNumber === null
      ? episodes
      : episodes.filter((episode) => episode.season_number === seasonNumber)
    watchedEps.value = new Set(
      filtered.flatMap((episode) => episode.season_number !== null && episode.episode_number !== null ? [episodeKey(episode.season_number, episode.episode_number)] : [])
    )
    watchedAtMap.value = new Map(
      filtered.flatMap((episode) => episode.season_number !== null && episode.episode_number !== null ? [[episodeKey(episode.season_number, episode.episode_number), episode.watched_at ?? ''] as const] : [])
    )
  }

  async function load(tmdbId: string | number, { seasonNumber = null, onError = (error) => console.error('Failed to load watched episodes:', error) }: LoadOptions = {}) {
    try {
      const response = await trackingAPI.getWatchedEpisodes(tmdbId)
      if (response?.episodes) {
        applyResponse(response, { seasonNumber })
      }
      return response
    } catch (error) {
      onError(error)
      return null
    }
  }

  return {
    watchedEps,
    watchedAtMap,
    isWatched,
    watchedAt,
    markLocally,
    unmarkLocally,
    applyResponse,
    load,
  }
}
