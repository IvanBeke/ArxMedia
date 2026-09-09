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
import { required } from '@/test-support/assertions'
import type { MediaResult } from '@/types/api'

const movie = { id: 42, media_type: 'movie' as const, tmdb_id: 42, user_status: { status: 'watched' as const } } as MediaResult & { tmdb_id: number }

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('MovieUnwatchDialog', () => {
  it('shows the movie copy when opened with a movie item', async () => {
    const wrapper = mount(MovieUnwatchDialog)
    wrapper.vm.open(movie)
    await nextTick()

    expect(wrapper.find('dialog').element.open).toBe(true)
    expect(wrapper.text()).toContain('Remove this movie from history?')
  })

  it('removes one history entry, patches the item status and emits unwatched', async () => {
    const onError = vi.fn()
    const wrapper = mount(MovieUnwatchDialog, { props: { onError } })

    wrapper.vm.open(movie)
    await nextTick()
    wrapper.findComponent(ConfirmDialog).vm.$emit('confirm')
    await flushPromises()

    expect(trackingAPI.removeFromHistory).toHaveBeenCalledWith({
      media_type: 'movie',
      tmdb_id: 42,
    })
    expect(required(movie.user_status, 'Movie user status').status).not.toBe('watched')
    expect(required(required(wrapper.emitted('unwatched'), 'Unwatched event')[0], 'Unwatched event payload')[0]).toBe(movie)
    expect(wrapper.find('dialog').element.open).toBe(false)
  })

  it('stays open without emitting when the API call fails', async () => {
    const onError = vi.fn()
    vi.mocked(trackingAPI.removeFromHistory).mockRejectedValueOnce(new Error('boom'))

    const wrapper = mount(MovieUnwatchDialog, { props: { onError } })
    wrapper.vm.open(movie)
    await nextTick()

    wrapper.findComponent(ConfirmDialog).vm.$emit('confirm')
    await flushPromises()

    expect(onError).toHaveBeenCalled()
    expect(wrapper.emitted('unwatched')).toBeUndefined()
    expect(wrapper.find('dialog').element.open).toBe(true)
  })
})
