import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import HistoryView from '@/views/HistoryView.vue'
import { WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import { useAuthStore } from '@/stores/auth'
import type { User, WatchEntry } from '@/types/api'

const { getHistory, deleteHistory, getWatchCount } = vi.hoisted(() => ({
  getHistory: vi.fn(),
  deleteHistory: vi.fn(),
  getWatchCount: vi.fn(),
}))

vi.mock('@/api', () => ({
  trackingAPI: { getHistory, deleteHistory },
  statsAPI: { getWatchCount },
}))

const HistoryMediaCardStub = {
  props: { entry: { type: Object, required: true } },
  template: '<div class="history-card">{{ entry.title }}</div>',
}

const PaginationControlsStub = {
  props: { page: Number, count: Number },
  template: '<div class="pagination-stub" />',
}

function historyEntry(overrides: Partial<WatchEntry> = {}): WatchEntry {
  return {
    id: 1,
    media_type: WATCH_ENTRY_MEDIA_TYPE.EPISODE,
    tmdb_id: 42,
    watched_at: '2026-01-01T20:00:00Z',
    season_number: 1,
    episode_number: 2,
    created_at: '2026-01-01T20:00:00Z',
    title: 'Filtered Episode',
    poster_path: null,
    poster_url: null,
    vote_average: 0,
    show_name: 'Example Show',
    episode_type: '',
    ...overrides,
  }
}

async function mountHistory(query: Record<string, string> = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/history', name: 'history', component: HistoryView },
      { path: '/search', name: 'search', component: { template: '<div />' } },
    ],
  })
  await router.push({ path: '/history', query })
  await router.isReady()

  const pinia = createPinia()
  useAuthStore(pinia).user = { username: 'alex' } as User
  const wrapper = mount(HistoryView, {
    global: {
      plugins: [router, pinia],
      stubs: {
        HistoryMediaCard: HistoryMediaCardStub,
        PaginationControls: PaginationControlsStub,
        RouterLink: RouterLinkStub,
      },
    },
  })
  await flushPromises()

  return { wrapper, router }
}

const withSignal = expect.objectContaining({ signal: expect.any(AbortSignal) })

describe('HistoryView item filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getHistory.mockResolvedValue({ count: 1, next: null, previous: null, results: [historyEntry()] })
    getWatchCount.mockResolvedValue({ movies_watched: 7, episodes_watched: 21 })
  })

  it('sends item filters from the URL to the history API', async () => {
    await mountHistory({
      media_type: 'episode',
      tmdb_id: '42',
      season_number: '1',
      episode_number: '2',
    })

    expect(getHistory).toHaveBeenCalledWith({
      media_type: 'episode',
      tmdb_id: '42',
      season_number: '1',
      episode_number: '2',
      order: 'newest',
      page: 1,
    }, withSignal)
  })

  it('shows the watched counts of the signed-in user in the header, whatever the filters', async () => {
    const { wrapper } = await mountHistory({ media_type: 'episode' })

    expect(getWatchCount).toHaveBeenCalledWith('alex')
    expect(wrapper.findAll('span.text-brand-400').slice(0, 2).map((value) => value.text())).toEqual(['7', '21'])
  })

  it('does not ask for the counts again when the list filters change', async () => {
    const { wrapper } = await mountHistory()
    getWatchCount.mockClear()

    await wrapper.findAll('button').find((button) => button.text().includes('Newest first'))?.trigger('click')
    await flushPromises()

    expect(getWatchCount).not.toHaveBeenCalled()
  })

  it('leaves the counts out of the header when they fail to load', async () => {
    getWatchCount.mockRejectedValue({ status: 500 })

    const { wrapper } = await mountHistory()

    expect(wrapper.findAll('span.text-brand-400')).toHaveLength(0)
    expect(wrapper.find('.history-card').exists()).toBe(true)
  })

  it('refreshes the counts after removing an entry', async () => {
    deleteHistory.mockResolvedValue(undefined)
    const { wrapper } = await mountHistory()
    // Differs from the previous 7 and 21 by more than the removed entry, as if the history changed elsewhere too.
    getWatchCount.mockResolvedValue({ movies_watched: 5, episodes_watched: 3 })

    wrapper.findComponent(HistoryMediaCardStub).vm.$emit('action:history-remove', historyEntry())
    await flushPromises()

    expect(deleteHistory).toHaveBeenCalledWith(1)
    expect(getWatchCount).toHaveBeenCalledTimes(2)
    expect(wrapper.findAll('span.text-brand-400').slice(0, 2).map((value) => value.text())).toEqual(['5', '3'])
  })

  it('preserves item filters when changing visible history controls', async () => {
    const { wrapper, router } = await mountHistory({
      media_type: 'episode',
      tmdb_id: '42',
      season_number: '1',
      episode_number: '2',
    })
    getHistory.mockClear()

    const sortButton = wrapper.findAll('button').find((button) => button.text().includes('Newest first'))
    expect(sortButton).toBeTruthy()
    await sortButton?.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.query).toMatchObject({
      media_type: 'episode',
      tmdb_id: '42',
      season_number: '1',
      episode_number: '2',
      order: 'oldest',
    })
    expect(getHistory).toHaveBeenCalledWith({
      media_type: 'episode',
      tmdb_id: '42',
      season_number: '1',
      episode_number: '2',
      order: 'oldest',
      page: 1,
    }, withSignal)
  })
})
