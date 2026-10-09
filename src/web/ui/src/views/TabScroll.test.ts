import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import TVDetailView from '@/views/TVDetailView.vue'
import { useAuthStore } from '@/stores/auth'
import { resolveScrollPosition } from '@/router'
import type { User } from '@/types/api'

const { getTV, getTVCredits, getTVRecommendations, getRatings, getWatchedEpisodes, getHistory } = vi.hoisted(() => ({
  getTV: vi.fn(),
  getTVCredits: vi.fn(),
  getTVRecommendations: vi.fn(),
  getRatings: vi.fn(),
  getWatchedEpisodes: vi.fn(),
  getHistory: vi.fn(),
}))

vi.mock('@/api', () => ({
  mediaAPI: { getTV, getTVCredits, getTVRecommendations },
  trackingAPI: {
    getRatings, getWatchedEpisodes, getHistory,
    markSeasonWatched: vi.fn().mockResolvedValue({ episodes: [] }),
    unmarkSeasonWatched: vi.fn().mockResolvedValue({ episodes: [] }),
    unmarkShowWatched: vi.fn().mockResolvedValue({}),
    dropMedia: vi.fn().mockResolvedValue({}),
    removeFromHistory: vi.fn().mockResolvedValue({}),
    rate: vi.fn().mockResolvedValue({}),
    markShowWatched: vi.fn().mockResolvedValue({ marked: 0, episodes: [] }),
  },
}))

const TEST_USER: User = {
  id: 1, username: 'tester', email: '', bio: '', avatar: null, location: '',
  website: '', preferred_region: 'US', account_visibility: 'public',
  followers_count: 0, following_count: 0, total_watched_movies: 0,
  total_watched_episodes: 0, created_at: '',
}

describe('detail tab scroll', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.scrollTo = vi.fn()
    getTV.mockResolvedValue({
      tmdb_id: 1399, name: 'Dark', overview: '', genres: [], poster_url: null,
      backdrop_url: null, first_air_date: '2017-12-01', last_air_date: '2020-06-27',
      number_of_seasons: 1, number_of_episodes: 3, vote_average: 8.4, vote_count: 100,
      language: 'de', status: 'Ended', networks: 'Netflix', episode_runtime: 60,
      seasons: [{ season_number: 1, name: 'Season 1', overview: '', poster_path: null, poster_url: null, air_date: '2017-12-01', episode_count: 3, vote_average: 8.1, vote_count: 15 }],
      user_status: { status: 'watching' }, watch_providers: null,
    })
    getTVCredits.mockResolvedValue({ cast: [], crew: [], guest_stars: [] })
    getTVRecommendations.mockResolvedValue({ results: [] })
    getRatings.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
    getWatchedEpisodes.mockResolvedValue({ episodes: [] })
    getHistory.mockResolvedValue({ results: [], count: 0, next: null, previous: null })
  })

  it('switching tabs triggers only tab-only navigations (scroll preserved)', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/tv/:id', name: 'tv-detail', component: TVDetailView },
        { path: '/tv/:id/season/:seasonNumber', name: 'season-detail', component: { template: '<div />' } },
      ],
      scrollBehavior: (to, from, saved) => resolveScrollPosition(to, from, saved),
    })
    await router.push('/tv/1399')
    await router.isReady()
    setActivePinia(createPinia())
    useAuthStore().user = TEST_USER

    const navigations: { path: string; query: Record<string, unknown> }[] = []
    router.afterEach((to) => navigations.push({ path: to.path, query: { ...to.query } }))

    const wrapper = mount(TVDetailView, { global: { plugins: [router, createPinia()], stubs: { WatchedDateTimePicker: true, ConfirmDialog: true, EpisodeUnwatchDialog: true, SeasonEpisodeList: true, AddToListPopover: true } } })
    await flushPromises()
    navigations.length = 0
    vi.mocked(window.scrollTo).mockClear()

    await wrapper.findAll('[role="tab"]').find((t) => t.text().includes('Seasons'))?.trigger('click')
    await flushPromises()

    expect(navigations.length).toBeGreaterThan(0)
    for (const nav of navigations) {
      expect(nav.path).toBe('/tv/1399')
      expect(Object.keys(nav.query)).toEqual(['tab'])
    }
    expect(window.scrollTo).not.toHaveBeenCalled()
  })
})

describe('detail tab scroll under late data', () => {
  it('deep link with ?tab= plus late recommendations never scrolls', async () => {
    let resolveRecs!: (v: unknown) => void
    getTVRecommendations.mockReturnValue(new Promise((resolve) => { resolveRecs = resolve }))
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/tv/:id', name: 'tv-detail', component: TVDetailView },
        { path: '/tv/:id/season/:seasonNumber', name: 'season-detail', component: { template: '<div />' } },
      ],
      scrollBehavior: (to, from, saved) => resolveScrollPosition(to, from, saved),
    })
    await router.push('/tv/1399?tab=more')
    await router.isReady()
    setActivePinia(createPinia())
    useAuthStore().user = TEST_USER

    const navigations: string[] = []
    router.afterEach((to) => navigations.push(to.fullPath))
    const wrapper = mount(TVDetailView, { global: { plugins: [router, createPinia()], stubs: { WatchedDateTimePicker: true, ConfirmDialog: true, EpisodeUnwatchDialog: true, SeasonEpisodeList: true, AddToListPopover: true } } })
    await flushPromises()
    navigations.length = 0
    vi.mocked(window.scrollTo).mockClear()

    // recommendations fail -> 'more' tab disappears while active
    resolveRecs({ results: [] })
    await flushPromises()
    // rapid tab switching
    for (const label of ['Seasons', 'Cast', 'Overview', 'Heatmap']) {
      await wrapper.findAll('[role="tab"]').find((t) => t.text().includes(label))?.trigger('click')
      await flushPromises()
    }

    for (const fullPath of navigations) {
      expect(fullPath.startsWith('/tv/1399?')).toBe(true)
      const query = Object.fromEntries(new URL(fullPath, 'http://x').searchParams)
      expect(Object.keys(query)).toEqual(['tab'])
    }
    expect(window.scrollTo).not.toHaveBeenCalled()
  })
})
