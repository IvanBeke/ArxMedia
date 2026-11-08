import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import DashboardView from '@/views/DashboardView.vue'
import FutureEpisodeCard from '@/components/FutureEpisodeCard.vue'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/types/api'

const { getStats, getActivity, getUpNext, getUpcoming, getJellyfinEpisodeLinks, markEpisodeWatched } = vi.hoisted(() => ({
  getStats: vi.fn(),
  getActivity: vi.fn(),
  getUpNext: vi.fn(),
  getUpcoming: vi.fn(),
  getJellyfinEpisodeLinks: vi.fn(),
  markEpisodeWatched: vi.fn(),
}))

vi.mock('@/api', () => ({
  trackingAPI: { getStats, getActivity, getUpNext, getUpcoming, deleteHistory: vi.fn(), markEpisodeWatched },
  integrationsAPI: { getJellyfinEpisodeLinks },
}))

const JELLYFIN_URL = 'https://jellyfin.example.com/web/index.html#/details?id=episode'

function upNextItem(tmdbId: number, season = 1, episode = 2) {
  return {
    tmdb_id: tmdbId, show_name: `Show ${tmdbId}`, poster_url: '', is_new: false, progress_percent: 10,
    episodes_left: 3, runtime_left_minutes: 90, runtime_left_has_unknown: false,
    next_episode: { name: 'Ep', episode_type: 'standard', season_number: season, episode_number: episode, runtime: 30 },
  }
}

async function mountView({ jellyfin = false } = {}) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { template: '<div />' } }] })
  setActivePinia(createPinia())
  useAuthStore().user = { integrations: { radarr: false, sonarr: false, jellyfin } } as User
  const wrapper = mount(DashboardView, {
    global: { plugins: [router], stubs: { HistoryMediaCard: true, FutureEpisodeCard: true } },
  })
  await flushPromises()
  return wrapper
}

describe('DashboardView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getStats.mockResolvedValue({ movies_watched: 2, episodes_watched: 5, shows_watching: 1, shows_watched: 3, average_rating: null, watch_time_minutes: 150 })
    getActivity.mockResolvedValue([])
    getUpNext.mockResolvedValue([])
    getUpcoming.mockResolvedValue([])
  })

  it('shows a section error instead of the empty state and retries', async () => {
    getUpNext.mockRejectedValueOnce({ detail: 'Request failed (500)', status: 500 })

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Could not load Up Next.')
    expect(wrapper.text()).not.toContain('My Shows is empty')
    expect(wrapper.text()).toContain('No upcoming episodes')

    await wrapper.get('[role="alert"] button').trigger('click')
    await flushPromises()

    expect(getUpNext).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('Could not load Up Next.')
    expect(wrapper.text()).toContain('My Shows is empty')
  })

  it('sets the document title', async () => {
    await mountView()

    expect(document.title).toBe('Dashboard · ArxMedia')
  })

  it('formats total watch time from the stats payload', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Watch time')
    expect(wrapper.text()).toContain('2h 30m')
  })

  it('shows zero watch time when nothing was watched yet', async () => {
    getStats.mockResolvedValueOnce({ movies_watched: 0, episodes_watched: 0, shows_watching: 0, shows_watched: 0, average_rating: null, watch_time_minutes: 0 })

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Watch time')
    expect(wrapper.text()).toContain('0m')
  })

  it('shows completed shows separately from shows still watching', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Shows Watching')
    expect(wrapper.text()).toContain('Shows Watched')
  })

  it('shows a section error instead of the activity list and retries', async () => {
    getActivity.mockRejectedValueOnce({ detail: 'Request failed (500)', status: 500 })

    const wrapper = await mountView()

    const alert = wrapper.findAll('[role="alert"]').find((node) => node.text().includes('Recent activity is unavailable'))
    expect(alert).toBeTruthy()
    await alert!.find('button').trigger('click')
    await flushPromises()

    expect(getActivity).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('Recent activity is unavailable')
  })

  describe('Jellyfin links on Up Next', () => {
    beforeEach(() => {
      getUpNext.mockResolvedValue([upNextItem(1), upNextItem(2)])
      markEpisodeWatched.mockResolvedValue({})
      getJellyfinEpisodeLinks.mockImplementation(async (refs: { tmdb_id: number }[]) => ({
        results: refs.map((ref) => ({ ...ref, url: ref.tmdb_id === 1 ? JELLYFIN_URL : null })),
      }))
    })

    it('passes each card its Jellyfin episode link once the links load', async () => {
      const wrapper = await mountView({ jellyfin: true })

      expect(getJellyfinEpisodeLinks).toHaveBeenCalledWith(
        [
          { tmdb_id: 1, season_number: 1, episode_number: 2 },
          { tmdb_id: 2, season_number: 1, episode_number: 2 },
        ],
        expect.any(Object),
      )
      const cards = wrapper.findAllComponents(FutureEpisodeCard)
      expect(cards.map((card) => card.props('jellyfinUrl'))).toEqual([JELLYFIN_URL, ''])
    })

    it('does not ask Jellyfin without access to it', async () => {
      const wrapper = await mountView()

      expect(getJellyfinEpisodeLinks).not.toHaveBeenCalled()
      expect(wrapper.findAllComponents(FutureEpisodeCard).map((card) => card.props('jellyfinUrl'))).toEqual(['', ''])
    })

    it('still shows the row when Jellyfin fails', async () => {
      getJellyfinEpisodeLinks.mockRejectedValue({ detail: 'down', status: 502 })

      const wrapper = await mountView({ jellyfin: true })

      expect(wrapper.findAllComponents(FutureEpisodeCard)).toHaveLength(2)
      expect(wrapper.text()).not.toContain('Could not load Up Next.')
    })

    it('looks the links up again after marking an episode watched', async () => {
      const wrapper = await mountView({ jellyfin: true })
      getUpNext.mockResolvedValue([upNextItem(1, 1, 3)])

      wrapper.findAllComponents(FutureEpisodeCard)[0]!.vm.$emit('watch')
      await flushPromises()

      expect(getJellyfinEpisodeLinks).toHaveBeenCalledTimes(2)
      expect(getJellyfinEpisodeLinks).toHaveBeenLastCalledWith(
        [{ tmdb_id: 1, season_number: 1, episode_number: 3 }],
        expect.any(Object),
      )
    })
  })
})
