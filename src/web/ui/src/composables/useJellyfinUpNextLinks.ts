import { ref } from 'vue'
import { integrationsAPI, type UpNextItem } from '@/api'
import { isAbortError, useLatestRequest } from '@/composables/useLatestRequest'
import { useAuthStore } from '@/stores/auth'
import type { JellyfinEpisodeRef } from '@/types/api'

const BATCH_SIZE = 50

function chunk<T>(items: T[], size: number): T[][] {
  return Array.from({ length: Math.ceil(items.length / size) }, (_, index) => items.slice(index * size, (index + 1) * size))
}

/** Jellyfin episode page for each Up Next show, by show TMDB id. Loads after the row so Jellyfin never delays it. */
export function useJellyfinUpNextLinks() {
  const auth = useAuthStore()
  const { next: nextRequest } = useLatestRequest()
  const urls = ref<Record<number, string>>({})

  async function load(items: UpNextItem[]) {
    const signal = nextRequest()
    if (!auth.user?.integrations.jellyfin) return
    const refs = items.flatMap((item): JellyfinEpisodeRef[] => item.next_episode
      ? [{ tmdb_id: item.tmdb_id, season_number: item.next_episode.season_number, episode_number: item.next_episode.episode_number }]
      : [])
    try {
      const responses = await Promise.all(chunk(refs, BATCH_SIZE).map((batch) => integrationsAPI.getJellyfinEpisodeLinks(batch, { signal })))
      urls.value = Object.fromEntries(
        responses.flatMap((response) => response.results).flatMap((result) => (result.url ? [[result.tmdb_id, result.url]] : [])),
      )
    } catch (error) {
      if (!isAbortError(error)) urls.value = {}
    }
  }

  return { urls, load }
}
