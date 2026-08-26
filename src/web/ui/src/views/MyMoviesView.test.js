import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia } from 'pinia'
import MyMoviesView from '@/views/MyMoviesView.vue'
import PaginationControls from '@/components/PaginationControls.vue'

const getMyMovies = vi.fn()

vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    trackingAPI: {
      getMyMovies: (...args) => getMyMovies(...args),
    },
    mediaAPI: {
      genres: vi.fn().mockResolvedValue([]),
    },
  }
})

function moviesPayload(count, rows) {
  return {
    count,
    results: Array.from({ length: rows }, (_, index) => ({ tmdb_id: index + 1 })),
    available_genres: [],
    total_watched_minutes: 0,
  }
}

async function mountView(initialQuery = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', name: 'catch-all', component: { template: '<div />' } }],
  })
  await router.push({ path: '/my-movies', query: initialQuery })
  await router.isReady()

  const wrapper = mount(MyMoviesView, {
    global: {
      plugins: [router, createPinia()],
      stubs: {
        MovieRow: true,
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

describe('MyMoviesView', () => {
  beforeEach(() => {
    getMyMovies.mockReset()
  })

  it('renders the header with the movie count', async () => {
    getMyMovies.mockResolvedValueOnce(moviesPayload(3, 3))

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('My Movies')
    expect(wrapper.text()).toContain('3 movies |')
    expect(getMyMovies).toHaveBeenCalledWith(expect.objectContaining({ sort: 'watched_date', direction: 'desc' }))
  })

  it('keeps the real page count after visiting a partial last page', async () => {
    getMyMovies
      .mockResolvedValueOnce(moviesPayload(47, 20))
      .mockResolvedValueOnce(moviesPayload(47, 7))

    const wrapper = await mountView()
    expect(lastTotalPages(wrapper)).toBe(3)

    wrapper.findComponent(PaginationControls).vm.$emit('go', 3)
    await flushPromises()

    expect(getMyMovies).toHaveBeenLastCalledWith(expect.objectContaining({ page: 3 }))
    expect(lastTotalPages(wrapper)).toBe(3)
    expect(pageNumberTexts(wrapper)).toEqual(['1', '2', '3'])
    expect(wrapper.text()).not.toContain('Could not load My Movies.')
  })

  it('falls back to page 1 when the API rejects the page as invalid', async () => {
    getMyMovies
      .mockRejectedValueOnce({ detail: 'Invalid page.', status: 404 })
      .mockResolvedValueOnce(moviesPayload(47, 20))

    const wrapper = await mountView({ page: '2' })

    expect(getMyMovies).toHaveBeenCalledTimes(2)
    expect(callPage(getMyMovies, 0)).toBe(2)
    expect(callPage(getMyMovies, 1)).toBe(1)
    expect(wrapper.text()).not.toContain('Could not load My Movies.')
    expect(lastTotalPages(wrapper)).toBe(3)
  })

  it('surfaces non-pagination errors as usual', async () => {
    getMyMovies.mockRejectedValueOnce({ detail: 'Server exploded.', status: 500 })

    const wrapper = await mountView({ page: '2' })

    expect(getMyMovies).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Server exploded.')
  })
})

function callPage(mockFn, callIndex) {
  return mockFn.mock.calls[callIndex][0].page
}
