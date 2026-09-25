import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import SeasonDetailView from '@/views/SeasonDetailView.vue'
import MediaHistoryTab from '@/components/MediaHistoryTab.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import SeasonEpisodeList from '@/components/SeasonEpisodeList.vue'
import EpisodeUnwatchDialog from '@/components/EpisodeUnwatchDialog.vue'
import WatchSplitButton from '@/components/WatchSplitButton.vue'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/types/api'

const { getSeason, getSeasonCredits, getWatchedEpisodes, getHistory, markEpisodeWatched, markSeasonWatched } = vi.hoisted(() => ({
  getSeason: vi.fn(),
  getSeasonCredits: vi.fn(),
  getWatchedEpisodes: vi.fn(),
  getHistory: vi.fn(),
  markEpisodeWatched: vi.fn(),
  markSeasonWatched: vi.fn(),
}))

vi.mock('@/api', () => {
  return {
    mediaAPI: {
      getSeason,
      getSeasonCredits,
    },
    trackingAPI: {
      getWatchedEpisodes,
      getHistory,
      markEpisodeWatched,
      unmarkEpisodeWatched: vi.fn().mockResolvedValue({}),
      markSeasonWatched,
    },
  }
})

const TMDB_ID = 30984
const SEASON_NUMBER = 2
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

function seasonPayload(watchedCount: number, total = 50) {
  return {
    tmdb_id: TMDB_ID,
    show_name: 'Dark',
    name: 'Season 2',
    overview: 'Season overview text',
    poster_url: null,
    vote_average: 8.4,
    vote_count: 0,
    air_date: '2021-06-21',
    credits: { cast: [{ credit_id: 'c1', name: 'Season Star', character: 'Lead', profile_path: null }], crew: [], guest_stars: [] },
    episodes: Array.from({ length: total }, (_, index) => ({
      episode_number: index + 1,
      name: `Episode ${index + 1}`,
      air_date: '',
      still_path: '',
    })),
    user_status: {
      status: 'watching',
      progress: {
        watched_episodes: watchedCount,
        total_episodes: total,
        percent: Math.round((watchedCount / total) * 100),
      },
    },
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

async function mountView(tab: string | null = 'episodes') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/tv/:id/season/:seasonNumber', name: 'season-detail', component: SeasonDetailView },
      { path: '/tv/:id', name: 'tv-detail', component: { template: '<div />' } },
      { path: '/history', name: 'history', component: { template: '<div />' } },
    ],
  })
  await router.push(tab ? `/tv/${TMDB_ID}/season/${SEASON_NUMBER}?tab=${tab}` : `/tv/${TMDB_ID}/season/${SEASON_NUMBER}`)
  await router.isReady()

  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().user = TEST_USER

  const wrapper = mount(SeasonDetailView, {
    global: {
      plugins: [router, pinia],
      stubs: {
        WatchMenu: { template: '<div><slot /></div>' },
        SeasonEpisodeList: true,
        WatchedDateTimePicker: true,
        EpisodeUnwatchDialog: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('SeasonDetailView progress', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getSeasonCredits.mockResolvedValue(null)
    markEpisodeWatched.mockResolvedValue({})
    markSeasonWatched.mockResolvedValue({})
  })

  it('renders the watched fraction and progress bar from backend user_status', async () => {
    getSeason.mockResolvedValue(seasonPayload(12))
    getWatchedEpisodes.mockResolvedValue(watchedPayload([[SEASON_NUMBER, 5]]))

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('12/50')
    expect(wrapper.findComponent(ProgressBar).props('pct')).toBe(24)
  })

  it('shows a history tab scoped to the season', async () => {
    getHistory.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })

    const wrapper = await mountView('overview')
    const historyTab = wrapper.findAll('[role="tab"]').find((tab) => tab.text().includes('History'))
    expect(historyTab).toBeTruthy()
    await historyTab?.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(MediaHistoryTab).exists()).toBe(true)
    expect(getHistory).toHaveBeenCalledWith({
      media_type: 'episode',
      tmdb_id: TMDB_ID,
      season_number: SEASON_NUMBER,
      order: 'newest',
      page: 1,
    })
  })

  it('increments the count optimistically when an unwatched episode is marked', async () => {
    getSeason.mockResolvedValue(seasonPayload(12))
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))

    const wrapper = await mountView()
    wrapper.findComponent(SeasonEpisodeList).vm.$emit('watch-option', {
      option: 'unknown',
      episodeNumber: 13,
      releaseDate: '',
    })
    await flushPromises()

    expect(markEpisodeWatched).toHaveBeenCalledWith(expect.objectContaining({
      tmdb_id: TMDB_ID,
      season_number: SEASON_NUMBER,
      episode_number: 13,
    }))
    expect(wrapper.text()).toContain('13/50')
    expect(wrapper.findComponent(ProgressBar).props('pct')).toBe(26)
  })

  it('does not double-count when re-dating an already watched episode', async () => {
    getSeason.mockResolvedValue(seasonPayload(12))
    getWatchedEpisodes.mockResolvedValue(watchedPayload([[SEASON_NUMBER, 7]]))

    const wrapper = await mountView()
    wrapper.findComponent(SeasonEpisodeList).vm.$emit('watch-option', {
      option: 'unknown',
      episodeNumber: 7,
      releaseDate: '',
    })
    await flushPromises()

    expect(wrapper.text()).toContain('12/50')
  })

  it('decrements the count when a watched episode is unwatched', async () => {
    getSeason.mockResolvedValue(seasonPayload(12))
    getWatchedEpisodes.mockResolvedValue(watchedPayload([[SEASON_NUMBER, 5], [SEASON_NUMBER, 6]]))

    const wrapper = await mountView()
    wrapper.findComponent(EpisodeUnwatchDialog).vm.$emit('unwatched', {
      seasonNumber: SEASON_NUMBER,
      episodeNumber: 5,
    })
    await flushPromises()

    expect(wrapper.text()).toContain('11/50')
  })

  it('recounts from the refreshed list after marking the whole season', async () => {
    getSeason.mockResolvedValue(seasonPayload(12))
    getWatchedEpisodes
      .mockResolvedValueOnce(watchedPayload([[SEASON_NUMBER, 5], [SEASON_NUMBER, 6]]))
      .mockResolvedValueOnce(
        watchedPayload(Array.from({ length: 50 }, (_, index) => [SEASON_NUMBER, index + 1])),
      )

    const wrapper = await mountView()
    expect(wrapper.text()).toContain('12/50')

    wrapper.findComponent(WatchSplitButton).vm.$emit('select', 'unknown')
    await flushPromises()

    expect(markSeasonWatched).toHaveBeenCalledWith(expect.objectContaining({
      tmdb_id: TMDB_ID,
      season_number: SEASON_NUMBER,
    }))
    expect(getWatchedEpisodes).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('50/50')
    expect(wrapper.findComponent(ProgressBar).props('pct')).toBe(100)
  })

  it('sends a full timestamp when marking a season on its release date', async () => {
    getSeason.mockResolvedValue(seasonPayload(12))
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))

    const wrapper = await mountView()
    wrapper.findComponent(WatchSplitButton).vm.$emit('select', 'release')
    await flushPromises()

    expect(markSeasonWatched).toHaveBeenCalledWith(expect.objectContaining({
      watched_at: '2021-06-21T00:00:00Z',
    }))
    expect(markSeasonWatched).not.toHaveBeenCalledWith(expect.objectContaining({
      use_release_date: true,
    }))
  })

  it('defaults to the overview tab and renders season overview there', async () => {
    getSeason.mockResolvedValue(seasonPayload(12))
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))

    const wrapper = await mountView(null)

    expect(wrapper.find('[role="tab"][aria-selected="true"]').text()).toContain('Overview')
    expect(wrapper.text()).toContain('Season overview text')
  })

  it('renders the show name link and provider rating in the hero', async () => {
    getSeason.mockResolvedValue(seasonPayload(12))
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))

    const wrapper = await mountView(null)

    expect(wrapper.text()).toContain('Dark')
    expect(wrapper.text()).toContain('8.4')
  })

  it('renders season cast in the cast tab with a link to full show cast', async () => {
    getSeason.mockResolvedValue(seasonPayload(12))
    getSeasonCredits.mockResolvedValue({
      cast: [{ credit_id: 'a1', name: 'Season Regular', character: 'Lead', profile_path: null, total_episode_count: 8 }],
      crew: [],
      guest_stars: [],
    })
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))

    const wrapper = await mountView('overview')

    const castTab = wrapper.findAll('[role="tab"]').find((tab) => tab.text().includes('Cast'))
    expect(castTab).toBeTruthy()
    await castTab?.trigger('click')

    expect(wrapper.text()).toContain('Season Regular')
    expect(wrapper.text()).toContain('8 eps')
    expect(wrapper.text()).not.toContain('View full show cast')
  })

  it('falls back to season credits when aggregate credits fail', async () => {
    getSeason.mockResolvedValue(seasonPayload(12))
    getSeasonCredits.mockRejectedValue(new Error('offline'))
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))

    const wrapper = await mountView(null)

    const castTab = wrapper.findAll('[role="tab"]').find((tab) => tab.text().includes('Cast'))
    await castTab?.trigger('click')

    expect(wrapper.text()).toContain('Season Star')
  })
})
