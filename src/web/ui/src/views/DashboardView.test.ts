import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import DashboardView from '@/views/DashboardView.vue'

const { getStats, getUpNext, getUpcoming } = vi.hoisted(() => ({
  getStats: vi.fn(),
  getUpNext: vi.fn(),
  getUpcoming: vi.fn(),
}))

vi.mock('@/api', () => ({
  trackingAPI: { getStats, getUpNext, getUpcoming, deleteHistory: vi.fn(), markEpisodeWatched: vi.fn() },
}))

async function mountView() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { template: '<div />' } }] })
  setActivePinia(createPinia())
  const wrapper = mount(DashboardView, {
    global: { plugins: [router], stubs: { HistoryMediaCard: true, FutureEpisodeCard: true } },
  })
  await flushPromises()
  return wrapper
}

describe('DashboardView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getStats.mockResolvedValue({ movies_watched: 2, episodes_watched: 5, shows_watching: 1, average_rating: null, recent_activity: [] })
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
})
