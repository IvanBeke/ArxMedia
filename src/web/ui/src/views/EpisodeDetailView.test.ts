import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia } from 'pinia'
import EpisodeDetailView from '@/views/EpisodeDetailView.vue'

const { getTV, getSeason, getEpisodeCredits, getWatchedEpisodes } = vi.hoisted(() => ({
  getTV: vi.fn(),
  getSeason: vi.fn(),
  getEpisodeCredits: vi.fn(),
  getWatchedEpisodes: vi.fn(),
}))

vi.mock('@/api', () => ({
  mediaAPI: { getTV, getSeason, getEpisodeCredits },
  trackingAPI: {
    getWatchedEpisodes,
    markEpisodeWatched: vi.fn().mockResolvedValue({}),
    unmarkEpisodeWatched: vi.fn().mockResolvedValue({}),
  },
}))

const TMDB_ID = 1399

const routedEpisodeView = {
  components: { EpisodeDetailView },
  template: '<RouterView v-slot="{ Component }"><component :is="Component" :key="$route.path" /></RouterView>',
}

const reusableEpisodeView = {
  components: { EpisodeDetailView },
  template: '<RouterView v-slot="{ Component }"><component :is="Component" /></RouterView>',
}

function episode(seasonNumber: number, episodeNumber: number) {
  return {
    id: TMDB_ID * 10000 + seasonNumber * 100 + episodeNumber,
    tmdb_id: TMDB_ID * 10000 + seasonNumber * 100 + episodeNumber,
    episode_number: episodeNumber,
    name: `Season ${seasonNumber} Episode ${episodeNumber}`,
    overview: '',
    still_path: null,
    still_url: null,
    air_date: '2026-01-01',
    air_time: null,
    broadcast_start: null,
    runtime: 45,
    vote_average: 8,
    vote_count: 100,
    episode_type: '',
    cast: [],
    guest_stars: [],
    crew: [],
  }
}

function showPayload(seasonNumbers = [1, 2, 3]) {
  return {
    id: 1,
    media_type: 'tv',
    tmdb_id: TMDB_ID,
    name: 'Navigation Show',
    overview: '',
    poster_path: null,
    backdrop_path: null,
    poster_url: null,
    backdrop_url: null,
    first_air_date: '2020-01-01',
    last_air_date: null,
    number_of_seasons: seasonNumbers.length,
    number_of_episodes: seasonNumbers.length * 2,
    language: 'en',
    status: 'Returning Series',
    networks: [],
    episode_runtime: 45,
    metadata_updated_at: '',
    seasons: seasonNumbers.map((seasonNumber) => ({
      id: seasonNumber,
      tmdb_id: seasonNumber,
      season_number: seasonNumber,
      name: `Season ${seasonNumber}`,
      overview: '',
      poster_path: null,
      poster_url: null,
      air_date: '2020-01-01',
      episode_count: 2,
      vote_average: 8,
      vote_count: 100,
    })),
  }
}

function seasonPayload(seasonNumber: number) {
  return {
    id: seasonNumber,
    tmdb_id: seasonNumber,
    season_number: seasonNumber,
    name: `Season ${seasonNumber}`,
    show_name: 'Navigation Show',
    overview: '',
    poster_path: null,
    poster_url: null,
    air_date: '2020-01-01',
    episode_count: 2,
    vote_average: 8,
    vote_count: 100,
    episodes: [episode(seasonNumber, 1), episode(seasonNumber, 2)],
  }
}

async function mountView(
  seasonNumber = 2,
  episodeNumber = 2,
  attachTo?: HTMLElement,
  keyed = true,
) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/tv/:id/season/:seasonNumber/episode/:episodeNumber',
        name: 'episode-detail',
        component: EpisodeDetailView,
      },
      {
        path: '/tv/:id/season/:seasonNumber',
        name: 'season-detail',
        component: { template: '<div />' },
      },
    ],
  })
  await router.push(`/tv/${TMDB_ID}/season/${seasonNumber}/episode/${episodeNumber}`)
  await router.isReady()

  const pinia = createPinia()
  const wrapper = mount(keyed ? routedEpisodeView : reusableEpisodeView, {
    attachTo,
    global: {
      plugins: [router, pinia],
      stubs: {
        WatchedDateTimePicker: true,
        EpisodeUnwatchDialog: true,
        WatchSplitButton: true,
        RatingBadge: true,
        ExternalLinks: true,
        CastGrid: true,
        EpisodeCodePill: true,
        EpisodeTypePill: true,
        SpoilerBlock: { template: '<div><slot /></div>' },
      },
    },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('EpisodeDetailView navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getTV.mockResolvedValue(showPayload())
    getSeason.mockImplementation((_showId: number, seasonNumber: number) => (
      Promise.resolve(seasonPayload(seasonNumber))
    ))
    getEpisodeCredits.mockResolvedValue(null)
    getWatchedEpisodes.mockResolvedValue({ episodes: [] })
  })

  it('links to the previous and next episodes across season boundaries', async () => {
    const { wrapper } = await mountView(2, 2)

    const previous = wrapper.get('[aria-label^="Previous episode:"]')
    const next = wrapper.get('[aria-label^="Next episode:"]')

    expect(previous.attributes('href')).toBe(`/tv/${TMDB_ID}/season/2/episode/1`)
    expect(previous.attributes('aria-label')).toContain('Season 2 Episode 1')
    expect(previous.find('svg').exists()).toBe(true)
    expect(next.attributes('href')).toBe(`/tv/${TMDB_ID}/season/3/episode/1`)
    expect(next.attributes('aria-label')).toContain('Season 3 Episode 1')
    expect(next.find('svg').exists()).toBe(true)
  })

  it('links backward to the last episode of the previous season', async () => {
    const { wrapper } = await mountView(2, 1)

    const previous = wrapper.get('[aria-label^="Previous episode:"]')
    expect(previous.attributes('href')).toBe(`/tv/${TMDB_ID}/season/1/episode/2`)
    expect(previous.attributes('aria-label')).toContain('Season 1 Episode 2')
  })

  it('reloads the episode view and moves focus when a navigation link changes the route', async () => {
    const attachTo = document.createElement('div')
    document.body.appendChild(attachTo)
    const { wrapper, router } = await mountView(2, 2, attachTo)

    await wrapper.get('[aria-label^="Next episode:"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe(`/tv/${TMDB_ID}/season/3/episode/1`)
    expect(wrapper.text()).toContain('Season 3 Episode 1')
    expect(document.activeElement).toBe(wrapper.get('h1').element)
    expect(getTV).toHaveBeenCalledTimes(2)

    wrapper.unmount()
    attachTo.remove()
  })

  it('reloads correctly when the route component is reused', async () => {
    const { wrapper, router } = await mountView(2, 2, undefined, false)

    await wrapper.get('[aria-label^="Next episode:"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe(`/tv/${TMDB_ID}/season/3/episode/1`)
    expect(wrapper.text()).toContain('Season 3 Episode 1')
    expect(getTV).toHaveBeenCalledTimes(2)
  })

  it('omits an unavailable navigation direction', async () => {
    getTV.mockResolvedValue(showPayload([2]))

    const { wrapper } = await mountView(2, 2)

    expect(wrapper.find('[aria-label^="Previous episode:"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label^="Next episode:"]').exists()).toBe(false)
  })

  it('renders the episode without waiting for adjacent navigation data', async () => {
    let resolveAdjacentSeason!: (season: ReturnType<typeof seasonPayload>) => void
    getSeason.mockImplementation((_showId: number, seasonNumber: number) => {
      if (seasonNumber === 3) {
        return new Promise<ReturnType<typeof seasonPayload>>((resolve) => {
          resolveAdjacentSeason = resolve
        })
      }
      return Promise.resolve(seasonPayload(seasonNumber))
    })

    const { wrapper } = await mountView(2, 2)

    expect(wrapper.find('.skeleton').exists()).toBe(false)
    expect(wrapper.text()).toContain('Season 2 Episode 2')
    expect(wrapper.find('[aria-label^="Next episode:"]').exists()).toBe(false)

    resolveAdjacentSeason(seasonPayload(3))
    await flushPromises()

    expect(wrapper.get('[aria-label^="Next episode:"]').attributes('aria-label')).toContain('Season 3 Episode 1')
  })

  it('keeps available navigation when an adjacent season fails to load', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    getTV.mockResolvedValue(showPayload([1, 2]))
    getSeason.mockImplementation((_showId: number, seasonNumber: number) => (
      seasonNumber === 1
        ? Promise.reject(new Error('Unavailable season'))
        : Promise.resolve(seasonPayload(seasonNumber))
    ))

    const { wrapper } = await mountView(2, 1)

    expect(wrapper.find('[aria-label^="Previous episode:"]').exists()).toBe(false)
    expect(wrapper.get('[aria-label^="Next episode:"]').attributes('aria-label')).toContain('Season 2 Episode 2')
    expect(errorSpy).toHaveBeenCalledWith(
      'Failed to load season 1 for episode navigation:',
      expect.any(Error),
    )
    errorSpy.mockRestore()
  })
})
