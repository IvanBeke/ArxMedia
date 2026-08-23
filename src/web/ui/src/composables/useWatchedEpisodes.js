import { ref } from 'vue'
import { trackingAPI } from '@/api'

export function episodeKey(seasonNumber, episodeNumber) {
  return `${seasonNumber}-${episodeNumber}`
}

export function useWatchedEpisodes() {
  const watchedEps = ref(new Set())
  const watchedAtMap = ref(new Map())

  function isWatched(seasonNumber, episodeNumber) {
    return watchedEps.value.has(episodeKey(seasonNumber, episodeNumber))
  }

  function watchedAt(seasonNumber, episodeNumber) {
    return watchedAtMap.value.get(episodeKey(seasonNumber, episodeNumber)) || ''
  }

  function markLocally(seasonNumber, episodeNumber, atIso) {
    watchedEps.value.add(episodeKey(seasonNumber, episodeNumber))
    watchedAtMap.value.set(episodeKey(seasonNumber, episodeNumber), atIso || '')
  }

  function unmarkLocally(seasonNumber, episodeNumber) {
    watchedEps.value.delete(episodeKey(seasonNumber, episodeNumber))
    watchedAtMap.value.delete(episodeKey(seasonNumber, episodeNumber))
  }

  function applyResponse(response, { seasonNumber = null } = {}) {
    const episodes = response?.episodes || []
    const filtered = seasonNumber === null
      ? episodes
      : episodes.filter(e => e.season_number === seasonNumber)
    watchedEps.value = new Set(
      filtered.map(e => episodeKey(e.season_number, e.episode_number))
    )
    watchedAtMap.value = new Map(
      filtered.map(e => [episodeKey(e.season_number, e.episode_number), e.watched_at || ''])
    )
  }

  async function load(tmdbId, { seasonNumber = null, onError = (error) => console.error('Failed to load watched episodes:', error) } = {}) {
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
