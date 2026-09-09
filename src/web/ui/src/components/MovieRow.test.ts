import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

const { rate } = vi.hoisted(() => ({ rate: vi.fn() }))

vi.mock('@/api', () => ({
  trackingAPI: {
    rate,
    getLists: vi.fn().mockResolvedValue([]),
    addToList: vi.fn(),
    createList: vi.fn(),
  },
}))

import MovieRow from '@/components/MovieRow.vue'
import { required } from '@/test-support/assertions'
import type { VueWrapper } from '@vue/test-utils'
import type { MediaCard } from '@/types/api'
import type { WatchEntryStatus } from '@/types/tracking'

type MovieRowItem = MediaCard & { genres: string[]; runtime: number; last_watched_at: string | null; user_rating: number; status: WatchEntryStatus; vote_count: number }

function makeItem(overrides: Partial<MovieRowItem> = {}): MovieRowItem {
  return {
    id: 42,
    media_type: 'movie',
    tmdb_id: 42,
    title: 'Blade Runner',
    poster_path: '/poster.jpg',
    poster_url: 'https://image.tmdb.org/t/p/w500/poster.jpg',
    release_date: '1982-06-25',
    runtime: 117,
    genres: ['Sci-Fi', 'Drama'],
    status: 'watched',
    user_rating: 9,
    vote_average: 8.0,
    vote_count: 1200,
    last_watched_at: null,
    user_status: { status: 'watched' },
    added_at: '2020-01-01T00:00:00Z',
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

function openManageMenu(wrapper: VueWrapper) {
  return wrapper.find('summary').trigger('click')
}

describe('MovieRow', () => {
  beforeEach(() => {
    rate.mockReset().mockResolvedValue({})
  })

  it('renders the movie link, status pill and meta line', async () => {
    const wrapper = await mountRow()

    const titleLink = wrapper.findAll('a').find((a) => a.text() === 'Blade Runner')
    expect(required(titleLink, 'Movie title link').attributes('href')).toBe('/movies/42')
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
    await required(rateButton, 'Rate button').trigger('click')

    const dialog = wrapper.find('dialog')
    expect(dialog.element.open).toBe(true)

    const stars = dialog.findAll('button[role="radio"]')
    await required(stars[7], 'Eight-star button').trigger('click')
    await flushPromises()

    expect(rate).toHaveBeenCalledWith({ media_type: 'movie', tmdb_id: 42, score: 8 })
    expect(wrapper.emitted('changed')).toBeTruthy()
    expect(dialog.element.open).toBe(false)
  })

  it('emits error with the API message when rating fails', async () => {
    rate.mockRejectedValueOnce({ detail: 'Rating rejected.' })
    const wrapper = await mountRow(makeItem({ user_rating: 0 }))
    await openManageMenu(wrapper)

    await required(wrapper
      .findAll('button.control-option')
      .find((button) => button.text().trim() === 'Rate'), 'Rate button').trigger('click')

    const dialog = wrapper.find('dialog')
    await required(dialog.findAll('button[role="radio"]')[9], 'Ten-star button').trigger('click')
    await flushPromises()

    expect(required(required(wrapper.emitted('error'), 'Error event')[0], 'Error event payload')[0]).toBe('Rating rejected.')
    expect(dialog.element.open).toBe(true)
  })
})
