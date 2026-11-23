import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { trackingAPI } from '@/api'
import TVDetailView from '@/views/TVDetailView.vue'
import MediaHistoryTab from '@/components/MediaHistoryTab.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import WatchSplitButton from '@/components/WatchSplitButton.vue'
import FlashToast from '@/components/FlashToast.vue'
import DetailHero from '@/components/DetailHero.vue'
import { useAuthStore } from '@/stores/auth'
import SonarrAction from '@/components/SonarrAction.vue'
import type { User } from '@/types/api'

const { getTV, refreshTV, getTVCredits, getTVRecommendations, getSeason, getRatings, getWatchedEpisodes, getHistory, getSonarrSeries, getSonarrOptions, getJellyfinLinks } = vi.hoisted(() => ({
  getTV: vi.fn(),
  refreshTV: vi.fn(),
  getTVCredits: vi.fn(),
  getTVRecommendations: vi.fn(),
  getSeason: vi.fn(),
  getRatings: vi.fn(),
  getWatchedEpisodes: vi.fn(),
  getHistory: vi.fn(),
  getSonarrSeries: vi.fn(),
  getSonarrOptions: vi.fn(),
  getJellyfinLinks: vi.fn(),
}))

vi.mock('@/api', () => {
  return {
    integrationsAPI: { getSonarrSeries, getSonarrOptions, addSonarrSeries: vi.fn(), removeSonarrSeries: vi.fn(), getJellyfinLinks },
    mediaAPI: {
      getTV,
      refreshTV,
      getTVCredits,
      getTVRecommendations,
      getSeason,
    },
    trackingAPI: {
      getRatings,
      getWatchedEpisodes,
      getHistory,
      markSeasonWatched: vi.fn().mockResolvedValue({ episodes: [] }),
      unmarkSeasonWatched: vi.fn().mockResolvedValue({ episodes: [] }),
      unmarkShowWatched: vi.fn().mockResolvedValue({}),
      markShowWatched: vi.fn().mockResolvedValue({ marked: 3, episodes: [] }),
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
  language: 'en',
  account_visibility: 'public',
  followers_count: 0,
  following_count: 0,
  total_watched_movies: 0,
  total_watched_episodes: 0,
  is_staff: false,
  integrations: { radarr: false, sonarr: false, jellyfin: false },
  created_at: '',
}

function progress(watched: number, total: number) {
  return { watched_episodes: watched, total_episodes: total, percent: total ? Math.floor((watched / total) * 100) : 0 }
}

function showPayload({ watched = 2, total = 3 } = {}) {
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
    episode_runtime: 60,
    seasons: [
      { season_number: 1, name: 'Season 1', overview: '', poster_path: null, poster_url: null, air_date: '2017-12-01', episode_count: 3, vote_average: 8.1, vote_count: 15, progress: progress(watched, total) },
    ],
    user_status: { status: 'watching', progress: progress(watched, total) },
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

async function mountView(authenticated: boolean, { sonarr = false, jellyfin = false } = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/tv/:id', name: 'tv-detail', component: TVDetailView },
      { path: '/tv/:id/season/:seasonNumber', name: 'season-detail', component: { template: '<div />' } },
      { path: '/history', name: 'history', component: { template: '<div />' } },
    ],
  })
  await router.push(`/tv/${TMDB_ID}`)
  await router.isReady()

  const pinia = createPinia()
  setActivePinia(pinia)
  if (authenticated) {
    useAuthStore().user = { ...TEST_USER, integrations: { ...TEST_USER.integrations, sonarr, jellyfin } }
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

function findButton(wrapper: VueWrapper, label: string) {
  return wrapper.findAll('button').find((button) => button.text() === label)
}

function multiSeasonPayload() {
  const payload = showPayload()
  payload.seasons = [
    { ...payload.seasons[0]!, season_number: 1, name: 'Season 1' },
    { ...payload.seasons[0]!, season_number: 2, name: 'Season 2' },
  ]
  return payload
}

async function openSeasonsTab() {
  const wrapper = await mountView(true)
  await wrapper.findAll('[role="tab"]').find((tab) => tab.text().includes('Seasons'))?.trigger('click')
  await flushPromises()
  return wrapper
}

describe('TVDetailView hero progress', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getTV.mockResolvedValue(showPayload())
    getTVCredits.mockResolvedValue({ cast: [], crew: [] })
    getTVRecommendations.mockResolvedValue({ results: [] })
    getRatings.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))
    getSeason.mockReset()
  })

  it('shows the watched fraction and progress bar for authenticated users', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([[1, 1], [1, 2]]))

    const wrapper = await mountView(true)

    expect(wrapper.text()).toContain('2/3 watched')
    const bars = wrapper.findAllComponents(ProgressBar)
    expect(bars.length).toBeGreaterThan(0)
    expect(bars[0]?.props('pct')).toBe(67)
  })

  it('hides the Sonarr button without the sonarr integration', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))

    const wrapper = await mountView(true)

    expect(wrapper.findAll('button').some((button) => button.text().includes('Sonarr'))).toBe(false)
    expect(wrapper.findComponent(SonarrAction).exists()).toBe(false)
    expect(getSonarrSeries).not.toHaveBeenCalled()
  })

  it('opens the Sonarr dialog from the Sonarr button and shows its toasts', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))
    getSonarrSeries.mockResolvedValue({ added: false })
    getSonarrOptions.mockResolvedValue({ root_folders: [], quality_profiles: [], tags: [] })

    const wrapper = await mountView(true, { sonarr: true })
    const button = wrapper.findAll('button').find((candidate) => candidate.text() === 'Add to Sonarr')
    expect(button).toBeTruthy()
    await button!.trigger('click')
    await flushPromises()

    expect(getSonarrSeries).toHaveBeenCalledWith(TMDB_ID, expect.any(Object))
    expect(wrapper.findComponent(SonarrAction).find('dialog').element.open).toBe(true)

    wrapper.findComponent(SonarrAction).vm.$emit('added')
    await flushPromises()
    expect(wrapper.text()).toContain('Dark added to Sonarr')

    wrapper.findComponent(SonarrAction).vm.$emit('removed')
    await flushPromises()
    expect(wrapper.text()).toContain('Dark removed from Sonarr')
  })

  it('hides the Jellyfin link without the jellyfin integration', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))

    const wrapper = await mountView(true)

    expect(wrapper.findAll('a').some((link) => link.text().includes('Jellyfin'))).toBe(false)
    expect(getJellyfinLinks).not.toHaveBeenCalled()
  })

  it('links the show to its Jellyfin page', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))
    getJellyfinLinks.mockResolvedValue({ show_url: 'https://jellyfin.example.com/web/#/details?id=dark', season_url: null, episode_url: null })

    const wrapper = await mountView(true, { jellyfin: true })

    const link = wrapper.findAll('a').find((candidate) => candidate.text() === 'Open in Jellyfin')
    expect(link?.attributes('href')).toBe('https://jellyfin.example.com/web/#/details?id=dark')
    expect(getJellyfinLinks).toHaveBeenCalledWith(TMDB_ID, {}, expect.any(Object))
  })

  it('does not offer the watchlist or remove history for a show being watched', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([[1, 1]]))

    const wrapper = await mountView(true)

    expect(wrapper.findAll('button').some((button) => button.text().includes('Watchlist'))).toBe(false)
    expect(trackingAPI.removeFromHistory).not.toHaveBeenCalled()
  })

  it('shows a retryable error when the show fails to load', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))
    getTV.mockRejectedValueOnce({ detail: 'Request failed (500)', status: 500 })

    const wrapper = await mountView(true)

    expect(wrapper.get('[role="alert"]').text()).toContain('Request failed (500)')
    await wrapper.get('[role="alert"] button').trigger('click')
    await flushPromises()

    expect(getTV).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('/3 watched')
  })

  it('shows an unavailable notice with retry when credits fail to load', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))
    getTVCredits.mockRejectedValueOnce(new Error('credits down'))

    const wrapper = await mountView(true)
    const castTab = wrapper.findAll('[role="tab"]').find((tab) => tab.text().includes('Cast'))
    await castTab!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('unavailable')
    const retry = wrapper.findAll('button').find((button) => button.text() === 'Try again')
    expect(retry).toBeTruthy()
    await retry!.trigger('click')
    await flushPromises()

    expect(getTVCredits).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('unavailable')
  })

  it('marks the whole show watched with a single request', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))
    getTV.mockResolvedValueOnce(showPayload({ watched: 0, total: 3 })).mockResolvedValueOnce(showPayload({ watched: 3, total: 3 }))
    vi.mocked(trackingAPI.markShowWatched).mockResolvedValue({ marked: 3, episodes: watchedPayload([[1, 1], [1, 2], [1, 3]]).episodes })

    const wrapper = await mountView(true)
    wrapper.findComponent(WatchSplitButton).vm.$emit('select', 'now')
    await flushPromises()

    expect(trackingAPI.markShowWatched).toHaveBeenCalledTimes(1)
    expect(trackingAPI.markShowWatched).toHaveBeenCalledWith({ tmdb_id: TMDB_ID, watched_at: 'now' })
    expect(trackingAPI.markSeasonWatched).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('3/3 watched')
  })

  it('shows action messages in a toast outside the hero so the hero does not resize', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))
    vi.mocked(trackingAPI.markShowWatched).mockRejectedValueOnce({ detail: 'Could not mark show.', status: 500 })

    const wrapper = await mountView(true)
    wrapper.findComponent(WatchSplitButton).vm.$emit('select', 'now')
    await flushPromises()

    expect(wrapper.findComponent(FlashToast).text()).toContain('Could not mark show.')
    expect(wrapper.findComponent(DetailHero).text()).not.toContain('Could not mark show.')
  })

  it('marks the whole show with each episode release date when release is chosen', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))

    const wrapper = await mountView(true)
    wrapper.findComponent(WatchSplitButton).vm.$emit('select', 'release')
    await flushPromises()

    expect(trackingAPI.markShowWatched).toHaveBeenCalledWith({ tmdb_id: TMDB_ID, watched_at: 'release_date' })
  })

  it('uses the backend released-only progress instead of counting watched or listed episodes', async () => {
    const payload = showPayload({ watched: 2, total: 3 })
    payload.number_of_episodes = 4
    payload.seasons[0]!.episode_count = 4
    getTV.mockResolvedValue(payload)
    getWatchedEpisodes.mockResolvedValue(watchedPayload([[1, 1], [1, 2], [1, 3], [1, 4], [0, 1]]))

    const wrapper = await mountView(true)

    expect(wrapper.text()).toContain('2/3 watched')
    expect(wrapper.text()).not.toContain('/4 watched')
    expect(wrapper.findAllComponents(ProgressBar)[0]?.props('pct')).toBe(67)
  })

  it('marks a season watched once every released episode is watched even if more are upcoming', async () => {
    const payload = showPayload({ watched: 3, total: 3 })
    payload.seasons[0]!.episode_count = 4
    getTV.mockResolvedValue(payload)
    getWatchedEpisodes.mockResolvedValue(watchedPayload([[1, 1], [1, 2], [1, 3]]))

    const wrapper = await mountView(true)
    await wrapper.findAll('[role="tab"]').find((tab) => tab.text().includes('Seasons'))?.trigger('click')
    await flushPromises()

    expect(wrapper.findAll('button').some((button) => button.text().includes('Mark watched'))).toBe(false)
    expect(wrapper.findAll('button').some((button) => button.text() === 'Watched')).toBe(true)
    expect(wrapper.text()).toContain('3/3 watched')
  })

  it('refreshes progress from the backend after marking a season', async () => {
    getTV.mockResolvedValueOnce(showPayload({ watched: 0, total: 3 })).mockResolvedValue(showPayload({ watched: 3, total: 3 }))
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))

    const wrapper = await mountView(true)
    await wrapper.findAll('[role="tab"]').find((tab) => tab.text().includes('Seasons'))?.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('0/3 watched')
    await wrapper.findAll('button').find((button) => button.text() === 'Mark watched')?.trigger('click')
    await flushPromises()

    expect(trackingAPI.markSeasonWatched).toHaveBeenCalledWith({ tmdb_id: TMDB_ID, season_number: 1 })
    expect(wrapper.text()).toContain('3/3 watched')
  })

  it('shows the season rating in the seasons list', async () => {
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))

    const wrapper = await mountView(true)
    const seasonsTab = wrapper.findAll('[role="tab"]').find((tab) => tab.text().includes('Seasons'))
    expect(seasonsTab).toBeTruthy()
    await seasonsTab?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('8.1')
  })

  it('shows per-season progress over released episodes only', async () => {
    const payload = showPayload()
    payload.seasons = [
      { ...payload.seasons[0]!, season_number: 1, name: 'Season 1', episode_count: 3, progress: progress(3, 3) },
      { ...payload.seasons[0]!, season_number: 2, name: 'Season 2', episode_count: 5, progress: progress(1, 4) },
      { ...payload.seasons[0]!, season_number: 10, name: 'Season 10', episode_count: 2, progress: progress(1, 2) },
    ]
    getTV.mockResolvedValue(payload)
    getWatchedEpisodes.mockResolvedValue(watchedPayload([[1, 1], [1, 2], [1, 3], [2, 1], [10, 1]]))

    const wrapper = await mountView(true)
    await wrapper.findAll('[role="tab"]').find((tab) => tab.text().includes('Seasons'))?.trigger('click')
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('3/3 watched')
    expect(text).toContain('1/4 watched')
    expect(text).toContain('1/2 watched')
  })

  it('expands and collapses every season from a single toggle', async () => {
    getTV.mockResolvedValue(multiSeasonPayload())
    getSeason.mockResolvedValue({ episodes: [{ episode_number: 1 }] })

    const wrapper = await openSeasonsTab()
    const toggleAll = findButton(wrapper, 'Expand all')
    expect(toggleAll).toBeTruthy()

    await toggleAll!.trigger('click')
    await flushPromises()

    expect(getSeason).toHaveBeenCalledTimes(2)
    expect(wrapper.findAll('season-episode-list-stub')).toHaveLength(2)

    const collapseAll = findButton(wrapper, 'Collapse all')
    expect(collapseAll).toBeTruthy()
    await collapseAll!.trigger('click')

    expect(wrapper.findAll('season-episode-list-stub')).toHaveLength(0)
    expect(findButton(wrapper, 'Expand all')).toBeDefined()
  })

  it('keeps several seasons open when expanded one by one', async () => {
    getTV.mockResolvedValue(multiSeasonPayload())
    getSeason.mockResolvedValue({ episodes: [{ episode_number: 1 }] })

    const wrapper = await openSeasonsTab()
    await wrapper.find('button[aria-label="Expand Season 1"]').trigger('click')
    await wrapper.find('button[aria-label="Expand Season 2"]').trigger('click')
    await flushPromises()

    expect(wrapper.findAll('season-episode-list-stub')).toHaveLength(2)
    expect(findButton(wrapper, 'Collapse all')).toBeDefined()
  })

  it('does not reload seasons that are already loaded when expanding all', async () => {
    getTV.mockResolvedValue(multiSeasonPayload())
    getSeason.mockResolvedValue({ episodes: [{ episode_number: 1 }] })

    const wrapper = await openSeasonsTab()
    await wrapper.find('button[aria-label="Expand Season 1"]').trigger('click')
    await flushPromises()
    await findButton(wrapper, 'Expand all')!.trigger('click')
    await flushPromises()

    expect(getSeason).toHaveBeenCalledTimes(2)
  })

  it('shows the empty state only for a season that fails to load when expanding all', async () => {
    getTV.mockResolvedValue(multiSeasonPayload())
    getSeason.mockImplementation((_id: number, seasonNumber: number) =>
      seasonNumber === 1 ? Promise.reject(new Error('boom')) : Promise.resolve({ episodes: [{ episode_number: 1 }] }),
    )

    const wrapper = await openSeasonsTab()
    await findButton(wrapper, 'Expand all')!.trigger('click')
    await flushPromises()

    expect(wrapper.findAll('season-episode-list-stub')).toHaveLength(1)
    expect(wrapper.text()).toContain('No episodes available for this season.')
  })

  it('retries a season that failed to load when it is expanded again', async () => {
    getTV.mockResolvedValue(multiSeasonPayload())
    getSeason.mockRejectedValueOnce(new Error('boom')).mockResolvedValue({ episodes: [{ episode_number: 1 }] })

    const wrapper = await openSeasonsTab()
    const chevron = () => wrapper.find('button[aria-label="Expand Season 1"]')
    await chevron().trigger('click')
    await flushPromises()
    expect(wrapper.findAll('season-episode-list-stub')).toHaveLength(0)

    await chevron().trigger('click')
    await chevron().trigger('click')
    await flushPromises()

    expect(getSeason).toHaveBeenCalledTimes(2)
    expect(wrapper.findAll('season-episode-list-stub')).toHaveLength(1)
  })

  it('reloads the open seasons after the metadata is refreshed', async () => {
    getTV.mockResolvedValue(multiSeasonPayload())
    getSeason.mockResolvedValue({ episodes: [{ episode_number: 1 }] })
    refreshTV.mockResolvedValue({})

    const wrapper = await openSeasonsTab()
    await findButton(wrapper, 'Expand all')!.trigger('click')
    await flushPromises()
    expect(getSeason).toHaveBeenCalledTimes(2)

    await wrapper.findAll('[role="tab"]').find((tab) => tab.text().includes('Overview'))?.trigger('click')
    await flushPromises()
    await findButton(wrapper, 'Update metadata from TMDB and TVMaze')!.trigger('click')
    await flushPromises()
    await wrapper.findAll('[role="tab"]').find((tab) => tab.text().includes('Seasons'))?.trigger('click')
    await flushPromises()

    expect(getSeason).toHaveBeenCalledTimes(4)
    expect(wrapper.findAll('season-episode-list-stub')).toHaveLength(2)
  })

  it('leaves the specials season out of the expand all toggle', async () => {
    const payload = multiSeasonPayload()
    payload.seasons.unshift({ ...payload.seasons[0]!, season_number: 0, name: 'Specials' })
    getTV.mockResolvedValue(payload)
    getSeason.mockResolvedValue({ episodes: [{ episode_number: 1 }] })

    const wrapper = await openSeasonsTab()
    await findButton(wrapper, 'Expand all')!.trigger('click')
    await flushPromises()

    expect(getSeason.mock.calls.map(([, seasonNumber]) => seasonNumber).sort()).toEqual([1, 2])
    expect(wrapper.findAll('season-episode-list-stub')).toHaveLength(2)
    expect(findButton(wrapper, 'Collapse all')).toBeDefined()

    await wrapper.find('button[aria-label="Expand Specials"]').trigger('click')
    await flushPromises()
    await findButton(wrapper, 'Collapse all')!.trigger('click')

    expect(wrapper.findAll('season-episode-list-stub')).toHaveLength(1)
  })

  it.each([
    ['a single season', () => showPayload()],
    ['a single season besides the specials', () => {
      const payload = showPayload()
      payload.seasons.unshift({ ...payload.seasons[0]!, season_number: 0, name: 'Specials' })
      return payload
    }],
  ])('hides the expand all toggle with %s', async (_label, buildPayload) => {
    getTV.mockResolvedValue(buildPayload())

    const wrapper = await openSeasonsTab()

    expect(findButton(wrapper, 'Expand all')).toBeUndefined()
    expect(findButton(wrapper, 'Collapse all')).toBeUndefined()
  })

  it('shows original title and stored language name when they differ', async () => {
    getTV.mockResolvedValueOnce({
      ...showPayload(),
      name: 'Oscura',
      original_title: 'Dark',
      language: 'de',
      language_name: 'German',
    })
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))

    const wrapper = await mountView(true)

    expect(wrapper.text()).toContain('Original title')
    expect(wrapper.text()).toContain('Dark')
    expect(wrapper.text()).toContain('German')
  })

  it('hides original title when identical and falls back to language code', async () => {
    getTV.mockResolvedValueOnce({
      ...showPayload(),
      name: 'Dark',
      original_title: 'Dark',
      language: 'de',
      language_name: '',
    })
    getWatchedEpisodes.mockResolvedValue(watchedPayload([]))

    const wrapper = await mountView(true)

    expect(wrapper.text()).not.toContain('Original title')
    expect(wrapper.text()).toContain('de')
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
