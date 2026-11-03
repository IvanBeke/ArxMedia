import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { useJellyfinUpNextLinks } from '@/composables/useJellyfinUpNextLinks'
import { useAuthStore } from '@/stores/auth'
import type { UpNextItem } from '@/api'
import type { User } from '@/types/api'

const { getJellyfinEpisodeLinks } = vi.hoisted(() => ({ getJellyfinEpisodeLinks: vi.fn() }))

vi.mock('@/api', () => ({ integrationsAPI: { getJellyfinEpisodeLinks } }))

function item(tmdbId: number, season: number | null = 1, episode = 1): UpNextItem {
  return {
    tmdb_id: tmdbId, show_name: `Show ${tmdbId}`, poster_url: '', is_new: false, progress_percent: 0,
    episodes_left: null, runtime_left_minutes: null, runtime_left_has_unknown: false,
    next_episode: season === null ? null : { name: 'Ep', episode_type: '', season_number: season, episode_number: episode, runtime: null },
  }
}

function signIn(jellyfin: boolean) {
  useAuthStore().user = { integrations: { radarr: false, sonarr: false, jellyfin } } as User
}

function mountComposable() {
  let api: ReturnType<typeof useJellyfinUpNextLinks> | undefined
  mount(defineComponent({
    setup() {
      api = useJellyfinUpNextLinks()
      return () => null
    },
  }))
  if (!api) throw new Error('composable not initialised')
  return api
}

describe('useJellyfinUpNextLinks', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getJellyfinEpisodeLinks.mockImplementation(async (refs: { tmdb_id: number }[]) => ({
      results: refs.map((ref) => ({ ...ref, url: ref.tmdb_id === 2 ? null : `https://jf/${ref.tmdb_id}` })),
    }))
  })

  it('does nothing when the user has no Jellyfin access', async () => {
    signIn(false)
    const { urls, load } = mountComposable()

    await load([item(1)])

    expect(getJellyfinEpisodeLinks).not.toHaveBeenCalled()
    expect(urls.value).toEqual({})
  })

  it('maps each show to its next episode link and skips shows without one', async () => {
    signIn(true)
    const { urls, load } = mountComposable()

    await load([item(1, 2, 5), item(2), item(3, null)])

    expect(getJellyfinEpisodeLinks).toHaveBeenCalledWith(
      [
        { tmdb_id: 1, season_number: 2, episode_number: 5 },
        { tmdb_id: 2, season_number: 1, episode_number: 1 },
      ],
      expect.any(Object),
    )
    expect(urls.value).toEqual({ 1: 'https://jf/1' })
  })

  it('splits long lists into batches of 50', async () => {
    signIn(true)
    const { urls, load } = mountComposable()

    await load(Array.from({ length: 120 }, (_, index) => item(index + 10)))

    expect(getJellyfinEpisodeLinks.mock.calls.map(([refs]) => refs.length)).toEqual([50, 50, 20])
    expect(Object.keys(urls.value)).toHaveLength(120)
  })

  it('shows no links when Jellyfin fails', async () => {
    signIn(true)
    const { urls, load } = mountComposable()
    await load([item(1)])
    getJellyfinEpisodeLinks.mockRejectedValue({ detail: 'down', status: 502 })

    await load([item(1)])
    await flushPromises()

    expect(urls.value).toEqual({})
  })

  it('replaces the links when loaded again', async () => {
    signIn(true)
    const { urls, load } = mountComposable()
    await load([item(1)])

    await load([item(4)])

    expect(urls.value).toEqual({ 4: 'https://jf/4' })
  })
})
