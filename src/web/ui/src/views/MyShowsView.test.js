import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia } from 'pinia'
import MyShowsView from '@/views/MyShowsView.vue'
import PaginationControls from '@/components/PaginationControls.vue'

const getMyShows = vi.fn()

vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    trackingAPI: {
      getMyShows: (...args) => getMyShows(...args),
      dropShow: vi.fn(),
      rate: vi.fn(),
    },
    mediaAPI: {
      genres: vi.fn().mockResolvedValue([]),
    },
  }
})

function showsPayload(count, rows) {
  return {
    count,
    results: Array.from({ length: rows }, (_, index) => ({ tmdb_id: index + 1 })),
    available_genres: [],
    available_provider_statuses: [],
    total_watched_minutes: 0,
  }
}

async function mountView(initialQuery = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', name: 'catch-all', component: { template: '<div />' } }],
  })
  await router.push({ path: '/my-shows', query: initialQuery })
  await router.isReady()

  const wrapper = mount(MyShowsView, {
    global: {
      plugins: [router, createPinia()],
      stubs: {
        ProgressRow: true,
        AddToListPopover: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}

function lastTotalPages(wrapper) {
  const events = wrapper.findComponent(PaginationControls).emitted('update:totalPages')
  return events[events.length - 1][0]
}

function pageNumberTexts(wrapper) {
  return wrapper
    .findAll('button')
    .map((button) => button.text())
    .filter((text) => /^\d+$/.test(text))
}

describe('MyShowsView pagination', () => {
  beforeEach(() => {
    getMyShows.mockReset()
  })

  it('keeps the real page count after visiting a partial last page', async () => {
    getMyShows
      .mockResolvedValueOnce(showsPayload(47, 20))
      .mockResolvedValueOnce(showsPayload(47, 7))

    const wrapper = await mountView()
    expect(lastTotalPages(wrapper)).toBe(3)

    wrapper.findComponent(PaginationControls).vm.$emit('go', 3)
    await flushPromises()

    expect(getMyShows).toHaveBeenLastCalledWith(expect.objectContaining({ page: 3 }))
    expect(lastTotalPages(wrapper)).toBe(3)
    expect(pageNumberTexts(wrapper)).toEqual(['1', '2', '3'])
    expect(wrapper.text()).not.toContain('Could not load My Shows.')
  })

  it('falls back to page 1 when the API rejects the page as invalid', async () => {
    getMyShows
      .mockRejectedValueOnce({ detail: 'Invalid page.', status: 404 })
      .mockResolvedValueOnce(showsPayload(47, 20))

    const wrapper = await mountView({ page: '2' })

    expect(getMyShows).toHaveBeenCalledTimes(2)
    expect(getMyOffersPage(getMyShows, 0)).toBe(2)
    expect(getMyOffersPage(getMyShows, 1)).toBe(1)
    expect(wrapper.text()).not.toContain('Could not load My Shows.')
    expect(lastTotalPages(wrapper)).toBe(3)
  })

  it('surfaces non-pagination errors as usual', async () => {
    getMyShows.mockRejectedValueOnce({ detail: 'Server exploded.', status: 500 })

    const wrapper = await mountView({ page: '2' })

    expect(getMyShows).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Server exploded.')
  })
})

function getMyOffersPage(mockFn, callIndex) {
  return mockFn.mock.calls[callIndex][0].page
}
