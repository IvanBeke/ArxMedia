import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import HistoryView from '@/views/HistoryView.vue'
import { WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import type { WatchEntry } from '@/types/api'

const { getHistory, getStats, deleteHistory } = vi.hoisted(() => ({
  getHistory: vi.fn(),
  getStats: vi.fn(),
  deleteHistory: vi.fn(),
}))

vi.mock('@/api', () => ({
  trackingAPI: { getHistory, getStats, deleteHistory },
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

describe('HistoryView item filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getStats.mockResolvedValue({ movies_watched: 1, episodes_watched: 1 })
    getHistory.mockResolvedValue({ count: 1, next: null, previous: null, results: [historyEntry()] })
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
    })
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
    })
  })
})
