import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

const rate = vi.fn()

vi.mock('@/api', () => ({
  trackingAPI: {
    rate: (...args) => rate(...args),
    getLists: vi.fn().mockResolvedValue([]),
    addToList: vi.fn(),
    createList: vi.fn(),
  },
}))

import MovieRow from '@/components/MovieRow.vue'

function makeItem(overrides = {}) {
  return {
    tmdb_id: 42,
    title: 'Blade Runner',
    poster_url: 'https://image.tmdb.org/t/p/w500/poster.jpg',
    release_date: '1982-06-25',
    runtime: 117,
    genres: ['Sci-Fi', 'Drama'],
    status: 'watched',
    user_rating: 9,
    vote_average: 8.0,
    vote_count: 1200,
    last_watched_at: null,
    ...overrides,
  }
}

async function mountRow(item = makeItem()) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', name: 'catch-all', component: { template: '<div />' } }],
  })
  await router.push('/')
  await router.isReady()

  const wrapper = mount(MovieRow, {
    props: { item },
    global: { plugins: [router, createPinia()] },
  })
  await flushPromises()
  return wrapper
}

function openManageMenu(wrapper) {
  return wrapper.find('summary').trigger('click')
}

describe('MovieRow', () => {
  beforeEach(() => {
    rate.mockReset().mockResolvedValue({})
  })

  it('renders the movie link, status pill and meta line', async () => {
    const wrapper = await mountRow()

    const titleLink = wrapper.findAll('a').find((a) => a.text() === 'Blade Runner')
    expect(titleLink.attributes('href')).toBe('/movies/42')
    expect(wrapper.text()).toContain('Watched')
    expect(wrapper.text()).toContain('1982')
    expect(wrapper.text()).toContain('117 min')
    expect(wrapper.text()).toContain('Sci-Fi, Drama')
  })

  it('rates the movie from the dialog and emits changed', async () => {
    const wrapper = await mountRow(makeItem({ user_rating: 0 }))
    await openManageMenu(wrapper)

    const rateButton = wrapper
      .findAll('button.control-option')
      .find((button) => button.text().trim() === 'Rate')
    await rateButton.trigger('click')

    const dialog = wrapper.find('dialog')
    expect(dialog.element.open).toBe(true)

    const stars = dialog.findAll('button[role="radio"]')
    await stars[7].trigger('click')
    await flushPromises()

    expect(rate).toHaveBeenCalledWith({ media_type: 'movie', tmdb_id: 42, score: 8 })
    expect(wrapper.emitted('changed')).toBeTruthy()
    expect(dialog.element.open).toBe(false)
  })

  it('emits error with the API message when rating fails', async () => {
    rate.mockRejectedValueOnce({ detail: 'Rating rejected.' })
    const wrapper = await mountRow(makeItem({ user_rating: 0 }))
    await openManageMenu(wrapper)

    await wrapper
      .findAll('button.control-option')
      .find((button) => button.text().trim() === 'Rate')
      .trigger('click')

    const dialog = wrapper.find('dialog')
    await dialog.findAll('button[role="radio"]')[9].trigger('click')
    await flushPromises()

    expect(wrapper.emitted('error')[0][0]).toBe('Rating rejected.')
    expect(dialog.element.open).toBe(true)
  })
})
