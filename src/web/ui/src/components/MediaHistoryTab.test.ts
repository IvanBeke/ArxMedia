import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import MediaHistoryTab from '@/components/MediaHistoryTab.vue'
import { WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import type { WatchEntry } from '@/types/api'

const { getHistory, deleteHistory } = vi.hoisted(() => ({
  getHistory: vi.fn(),
  deleteHistory: vi.fn(),
}))

vi.mock('@/api', () => ({
  trackingAPI: { getHistory, deleteHistory },
}))

const HistoryMediaCardStub = {
  props: {
    entry: { type: Object, required: true },
    showRemoveAction: { type: Boolean, default: false },
    removeLoading: { type: Boolean, default: false },
    removeConfirmText: { type: String, default: '' },
  },
  emits: ['action:history-remove'],
  template: `
    <div class="history-card">
      {{ entry.title }}
      <button v-if="showRemoveAction" class="remove-action" :disabled="removeLoading" @click="$emit('action:history-remove', entry)">Remove</button>
    </div>
  `,
}

function historyEntry(overrides: Partial<WatchEntry> = {}): WatchEntry {
  return {
    id: 1,
    media_type: WATCH_ENTRY_MEDIA_TYPE.EPISODE,
    tmdb_id: 100,
    watched_at: '2026-01-01T20:00:00Z',
    season_number: 1,
    episode_number: 2,
    created_at: '2026-01-01T20:00:00Z',
    title: 'The Finale',
    poster_path: null,
    poster_url: null,
    vote_average: 0,
    show_name: 'Example Show',
    episode_type: '',
    ...overrides,
  }
}

function mountTab() {
  return mount(MediaHistoryTab, {
    props: {
      filter: {
        media_type: WATCH_ENTRY_MEDIA_TYPE.EPISODE,
        tmdb_id: 100,
        season_number: 1,
        episode_number: 2,
      },
    },
    global: {
      plugins: [createPinia()],
      stubs: {
        HistoryMediaCard: HistoryMediaCardStub,
        RouterLink: RouterLinkStub,
      },
    },
  })
}

describe('MediaHistoryTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    deleteHistory.mockResolvedValue(undefined)
  })

  it('loads the newest page and limits the quick view to 20 cards', async () => {
    const results = Array.from({ length: 25 }, (_, index) => historyEntry({
      id: index + 1,
      title: `Episode ${index + 1}`,
    }))
    getHistory.mockResolvedValue({ count: 25, next: null, previous: null, results })

    const wrapper = mountTab()
    await flushPromises()

    expect(getHistory).toHaveBeenCalledWith({
      media_type: 'episode',
      tmdb_id: 100,
      season_number: 1,
      episode_number: 2,
      order: 'newest',
      page: 1,
    })
    expect(wrapper.findAll('.history-card')).toHaveLength(20)
    expect(wrapper.text()).toContain('25 entries')
    expect(wrapper.findComponent(RouterLinkStub).props('to')).toEqual({
      name: 'history',
      query: {
        media_type: 'episode',
        tmdb_id: '100',
        season_number: '1',
        episode_number: '2',
      },
    })
  })

  it('exposes the history-card remove action and refreshes after deletion', async () => {
    getHistory
      .mockResolvedValueOnce({ count: 1, next: null, previous: null, results: [historyEntry()] })
      .mockResolvedValueOnce({ count: 0, next: null, previous: null, results: [] })

    const wrapper = mountTab()
    await flushPromises()

    const removeAction = wrapper.find('.remove-action')
    expect(removeAction.exists()).toBe(true)
    await removeAction.trigger('click')
    await flushPromises()

    expect(deleteHistory).toHaveBeenCalledWith(1)
    expect(getHistory).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('No watch history for this item yet.')
  })

  it('shows an empty state when the item has no history', async () => {
    getHistory.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })

    const wrapper = mountTab()
    await flushPromises()

    expect(wrapper.text()).toContain('No watch history for this item yet.')
  })

  it('shows an error state and retries the request', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    getHistory
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({ count: 1, next: null, previous: null, results: [historyEntry()] })

    const wrapper = mountTab()
    await flushPromises()

    expect(wrapper.text()).toContain('Could not load watch history.')
    const retry = wrapper.findAll('button').find((button) => button.text() === 'Try again')
    expect(retry).toBeTruthy()
    await retry?.trigger('click')
    await flushPromises()

    expect(getHistory).toHaveBeenCalledTimes(2)
    expect(wrapper.findAll('.history-card')).toHaveLength(1)
    consoleError.mockRestore()
  })
})
