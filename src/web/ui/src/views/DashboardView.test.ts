import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import DashboardView from '@/views/DashboardView.vue'

const { getStats, getActivity, getUpNext, getUpcoming } = vi.hoisted(() => ({
  getStats: vi.fn(),
  getActivity: vi.fn(),
  getUpNext: vi.fn(),
  getUpcoming: vi.fn(),
}))

vi.mock('@/api', () => ({
  trackingAPI: { getStats, getActivity, getUpNext, getUpcoming, deleteHistory: vi.fn(), markEpisodeWatched: vi.fn() },
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
})
