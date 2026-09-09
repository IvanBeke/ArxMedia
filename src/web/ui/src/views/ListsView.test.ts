import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ListsView from '@/views/ListsView.vue'

const getLists = vi.hoisted(() => vi.fn())

vi.mock('@/api', () => ({
  authAPI: { searchUsers: vi.fn() },
  trackingAPI: { getLists },
}))

describe('ListsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('renders lists from a paginated API response', async () => {
    getLists.mockResolvedValue({
      count: 3,
      next: null,
      previous: null,
      results: [
        { id: 1, name: 'First', description: '', privacy: 'public', item_count: 0, created_at: '2026-01-01T00:00:00Z' },
        { id: 2, name: 'Second', description: '', privacy: 'private', item_count: 1, created_at: '2026-01-01T00:00:00Z' },
        { id: 3, name: 'Third', description: '', privacy: 'public', item_count: 2, created_at: '2026-01-01T00:00:00Z' },
      ],
    })

    const wrapper = mount(ListsView, {
      global: {
        plugins: [createPinia()],
        stubs: { RouterLink: { template: '<a><slot /></a>' } },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('First')
    expect(wrapper.text()).toContain('Second')
    expect(wrapper.text()).toContain('Third')
    expect(wrapper.text()).not.toContain('No lists yet')
  })
})
