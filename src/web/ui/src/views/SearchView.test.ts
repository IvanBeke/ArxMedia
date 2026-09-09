import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia } from 'pinia'
import SearchView from '@/views/SearchView.vue'

const { search, trending } = vi.hoisted(() => ({
  search: vi.fn(),
  trending: vi.fn(),
}))

vi.mock('@/api', () => ({
  authAPI: { searchUsers: vi.fn() },
  mediaAPI: { search, trending },
}))

async function mountView(initialQuery: Record<string, string> = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/search', name: 'search', component: SearchView }],
  })
  await router.push({ path: '/search', query: initialQuery })
  await router.isReady()

  const wrapper = mount(SearchView, {
    global: {
      plugins: [router, createPinia()],
      stubs: {
        MediaCard: { template: '<div class="media-card" />' },
        UserList: true,
        PaginationControls: true,
      },
    },
  })
  await flushPromises()
  return { router, wrapper }
}

describe('SearchView', () => {
  beforeEach(() => {
    search.mockReset()
    trending.mockReset().mockResolvedValue({ results: [{ id: 1 }] })
  })

  it('keeps trending cards visible while drafting a search', async () => {
    const { wrapper } = await mountView()
    const input = wrapper.find('input')

    await input.setValue('batman')
    await flushPromises()

    expect(wrapper.text()).toContain('Trending Right Now')
    expect(wrapper.findAll('.media-card')).toHaveLength(2)
    expect(search).not.toHaveBeenCalled()
  })

  it('searches only after submitting the draft query', async () => {
    const { wrapper, router } = await mountView()
    const input = wrapper.find('input')
    search.mockResolvedValue({ results: [], total_pages: 1, total_results: 0, page: 1 })

    await input.setValue('batman')
    expect(search).not.toHaveBeenCalled()

    await input.trigger('keydown.enter')
    await flushPromises()

    expect(search).toHaveBeenCalledWith('batman', 'multi', 1)
    expect(router.currentRoute.value.query.q).toBe('batman')
  })

  it('returns to Discover when the submitted search is cleared', async () => {
    const { wrapper, router } = await mountView({ q: 'batman' })
    await flushPromises()

    await wrapper.find('button[aria-label="Clear search"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.query.q).toBeUndefined()
    expect(wrapper.text()).toContain('Discover')
    expect(wrapper.text()).toContain('Trending Right Now')
  })
})
