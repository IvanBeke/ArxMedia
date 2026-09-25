import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import TVDetailView from '@/views/TVDetailView.vue'
import MediaHistoryTab from '@/components/MediaHistoryTab.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/types/api'

const { getTV, getTVCredits, getTVRecommendations, getRatings, getWatchedEpisodes, getHistory } = vi.hoisted(() => ({
  getTV: vi.fn(),
  getTVCredits: vi.fn(),
  getTVRecommendations: vi.fn(),
  getRatings: vi.fn(),
  getWatchedEpisodes: vi.fn(),
  getHistory: vi.fn(),
}))

vi.mock('@/api', () => {
  return {
    mediaAPI: {
      getTV,
      getTVCredits,
      getTVRecommendations,
    },
    trackingAPI: {
      getRatings,
      getWatchedEpisodes,
      getHistory,
      markSeasonWatched: vi.fn().mockResolvedValue({ episodes: [] }),
      unmarkSeasonWatched: vi.fn().mockResolvedValue({ episodes: [] }),
      unmarkShowWatched: vi.fn().mockResolvedValue({}),
      dropMedia: vi.fn().mockResolvedValue({}),
      removeFromHistory: vi.fn().mockResolvedValue({}),
      rate: vi.fn().mockResolvedValue({}),
    },
  }
})

const TMDB_ID = 1399
const TEST_USER: User = {
  id: 1,
  username: 'tester',
  email: '',
  bio: '',
  avatar: null,
  location: '',
  website: '',
  preferred_region: 'US',
  account_visibility: 'public',
  followers_count: 0,
  following_count: 0,
  total_watched_movies: 0,
  total_watched_episodes: 0,
  created_at: '',
}

function showPayload() {
  return {
    tmdb_id: TMDB_ID,
    name: 'Dark',
    overview: 'A missing child...',
    genres: [],
    poster_url: null,
    backdrop_url: null,
    first_air_date: '2017-12-01',
    last_air_date: '2020-06-27',
    number_of_seasons: 1,
    number_of_episodes: 3,
    vote_average: 8.4,
    vote_count: 100,
    language: 'de',
    status: 'Ended',
    networks: 'Netflix',
    episode_runtime: 60,
    seasons: [
      { season_number: 1, name: 'Season 1', overview: '', poster_path: null, poster_url: null, air_date: '2017-12-01', episode_count: 3, vote_average: 8.1, vote_count: 15 },
    ],
    user_status: { status: 'watching' },
    watch_providers: null,
  }
}

function watchedPayload(pairs: [number, number][]) {
  return {
    episodes: pairs.map(([seasonNumber, episodeNumber]) => ({
      season_number: seasonNumber,
      episode_number: episodeNumber,
      watched_at: '2026-08-01T10:00:00Z',
    })),
  }
}

async function mountView(authenticated: boolean) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/tv/:id', name: 'tv-detail', component: TVDetailView },
      { path: '/history', name: 'history', component: { template: '<div />' } },
    ],
  })
  await router.push(`/tv/${TMDB_ID}`)
  await router.isReady()

  const pinia = createPinia()
  setActivePinia(pinia)
  if (authenticated) {
    useAuthStore().user = TEST_USER
  }

  const wrapper = mount(TVDetailView, {
    global: {
      plugins: [router, pinia],
      stubs: {
        WatchedDateTimePicker: true,
        ConfirmDialog: true,
        EpisodeUnwatchDialog: true,
        SeasonEpisodeList: true,
        AddToListPopover: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('TVDetailView hero progress', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getTV.mockResolvedValue(showPayload())
    getTVCredits.mockResolvedValue({ cast: [], crew: [], guest_stars: [] })
    getTVRecommendations.mockResolvedValue({ results: [] })
    getRatings.mockResolvedValue([])
  })

  it('shows the watched fraction and progress bar for authenticated users', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([[1, 1], [1, 2]]))

    const wrapper = await mountView(true)

    expect(wrapper.text()).toContain('2/3 watched')
    const bars = wrapper.findAllComponents(ProgressBar)
    expect(bars.length).toBeGreaterThan(0)
    expect(bars[0]?.props('pct')).toBe(67)
  })

  it('excludes specials from the watched count', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([[1, 1], [1, 2], [0, 1]]))

    const wrapper = await mountView(true)

    expect(wrapper.text()).toContain('2/3 watched')
  })

  it('shows the season rating in the seasons list', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))

    const wrapper = await mountView(true)
    const seasonsTab = wrapper.findAll('[role="tab"]').find((tab) => tab.text().includes('Seasons'))
    expect(seasonsTab).toBeTruthy()
    await seasonsTab?.trigger('click')

    expect(wrapper.text()).toContain('8.1')
  })

  it('shows a history tab scoped to the show', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([[1, 1]]))
    getHistory.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })

    const wrapper = await mountView(true)
    const historyTab = wrapper.findAll('[role="tab"]').find((tab) => tab.text().includes('History'))
    expect(historyTab).toBeTruthy()
    await historyTab?.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(MediaHistoryTab).exists()).toBe(true)
    expect(getHistory).toHaveBeenCalledWith({
      media_type: 'episode',
      tmdb_id: TMDB_ID,
      order: 'newest',
      page: 1,
    })
  })

  it('falls back to plain episode counts without a progress bar for guests', async () => {
    const wrapper = await mountView(false)

    expect(wrapper.text()).toContain('3 Episodes')
    expect(wrapper.text()).not.toContain('watched')
    expect(wrapper.findComponent(ProgressBar).exists()).toBe(false)
  })
})
