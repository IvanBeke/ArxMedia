import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'

vi.mock('@/api', () => ({
  trackingAPI: {
    addToHistory: vi.fn().mockResolvedValue({}),
    removeFromHistory: vi.fn().mockResolvedValue({}),
    markEpisodeWatched: vi.fn().mockResolvedValue({}),
    unmarkEpisodeWatched: vi.fn().mockResolvedValue({}),
    unmarkShowWatched: vi.fn().mockResolvedValue({}),
    addToWatchlist: vi.fn().mockResolvedValue({}),
    removeFromWatchlist: vi.fn().mockResolvedValue({}),
  },
}))

import { trackingAPI } from '@/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import MovieUnwatchDialog from '@/components/MovieUnwatchDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('MovieUnwatchDialog', () => {
  it('shows the movie copy when opened with a movie item', async () => {
    const wrapper = mount(MovieUnwatchDialog)
    wrapper.vm.open({ tmdb_id: 42 })
    await nextTick()

    expect(wrapper.find('dialog').element.open).toBe(true)
    expect(wrapper.text()).toContain('Remove this movie from history?')
  })

  it('removes one history entry, patches the item status and emits unwatched', async () => {
    const onError = vi.fn()
    const movie = { tmdb_id: 42, user_status: { status: 'watched' } }
    const wrapper = mount(MovieUnwatchDialog, { props: { onError } })

    wrapper.vm.open(movie)
    await nextTick()
    wrapper.findComponent(ConfirmDialog).vm.$emit('confirm')
    await flushPromises()

    expect(trackingAPI.removeFromHistory).toHaveBeenCalledWith({
      media_type: 'movie',
      tmdb_id: 42,
    })
    expect(movie.user_status.status).not.toBe('watched')
    expect(wrapper.emitted('unwatched')[0][0]).toBe(movie)
    expect(wrapper.find('dialog').element.open).toBe(false)
  })

  it('stays open without emitting when the API call fails', async () => {
    const onError = vi.fn()
    trackingAPI.removeFromHistory.mockRejectedValueOnce(new Error('boom'))

    const wrapper = mount(MovieUnwatchDialog, { props: { onError } })
    wrapper.vm.open({ tmdb_id: 42 })
    await nextTick()

    wrapper.findComponent(ConfirmDialog).vm.$emit('confirm')
    await flushPromises()

    expect(onError).toHaveBeenCalled()
    expect(wrapper.emitted('unwatched')).toBeUndefined()
    expect(wrapper.find('dialog').element.open).toBe(true)
  })
})
