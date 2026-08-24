import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import SeasonDetailView from '@/views/SeasonDetailView.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import SeasonEpisodeList from '@/components/SeasonEpisodeList.vue'
import EpisodeUnwatchDialog from '@/components/EpisodeUnwatchDialog.vue'
import WatchMenu from '@/components/WatchMenu.vue'
import { useAuthStore } from '@/stores/auth'

const getSeason = vi.fn()
const getWatchedEpisodes = vi.fn()
const markEpisodeWatched = vi.fn()
const markSeasonWatched = vi.fn()

vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    mediaAPI: {
      ...actual.mediaAPI,
      getSeason: (...args) => getSeason(...args),
    },
    trackingAPI: {
      ...actual.trackingAPI,
      getWatchedEpisodes: (...args) => getWatchedEpisodes(...args),
      markEpisodeWatched: (...args) => markEpisodeWatched(...args),
      unmarkEpisodeWatched: vi.fn().mockResolvedValue({}),
      markSeasonWatched: (...args) => markSeasonWatched(...args),
    },
  }
})

const TMDB_ID = 30984
const SEASON_NUMBER = 2

function seasonPayload(watchedCount, total = 50) {
  return {
    tmdb_id: TMDB_ID,
    show_name: 'Dark',
    name: 'Season 2',
    air_date: '2021-06-21',
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

function watchedPayload(pairs) {
  return {
    episodes: pairs.map(([seasonNumber, episodeNumber]) => ({
      season_number: seasonNumber,
      episode_number: episodeNumber,
      watched_at: '2026-08-01T10:00:00Z',
    })),
  }
}

async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/tv/:id/season/:seasonNumber', name: 'season-detail', component: SeasonDetailView },
      { path: '/tv/:id', name: 'tv-detail', component: { template: '<div />' } },
    ],
  })
  await router.push(`/tv/${TMDB_ID}/season/${SEASON_NUMBER}`)
  await router.isReady()

  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().user = { username: 'tester' }

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

    wrapper.findComponent(WatchMenu).vm.$emit('select', 'unknown')
    await flushPromises()

    expect(markSeasonWatched).toHaveBeenCalledWith(expect.objectContaining({
      tmdb_id: TMDB_ID,
      season_number: SEASON_NUMBER,
    }))
    expect(getWatchedEpisodes).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('50/50')
    expect(wrapper.findComponent(ProgressBar).props('pct')).toBe(100)
  })
})
