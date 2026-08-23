import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'

vi.mock('@/api', () => ({
  trackingAPI: {
    unmarkEpisodeWatched: vi.fn().mockResolvedValue({}),
  },
}))

import { trackingAPI } from '@/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EpisodeUnwatchDialog from '@/components/EpisodeUnwatchDialog.vue'

const TARGET = { tmdbId: 37854, seasonNumber: 2, episodeNumber: 5 }

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('EpisodeUnwatchDialog', () => {
  it('shows the episode copy when opened', async () => {
    const wrapper = mount(EpisodeUnwatchDialog)
    wrapper.vm.open(TARGET)
    await nextTick()

    expect(wrapper.find('dialog').element.open).toBe(true)
    expect(wrapper.text()).toContain('Remove this episode from history?')
    expect(wrapper.text()).toContain('This will remove this episode from your watched history.')
  })

  it('unmarks the episode and emits unwatched on confirm', async () => {
    const wrapper = mount(EpisodeUnwatchDialog)
    wrapper.vm.open(TARGET)
    await nextTick()

    wrapper.findComponent(ConfirmDialog).vm.$emit('confirm')
    await flushPromises()

    expect(trackingAPI.unmarkEpisodeWatched).toHaveBeenCalledWith({
      tmdb_id: 37854,
      season_number: 2,
      episode_number: 5,
    })
    expect(wrapper.emitted('unwatched')[0][0]).toEqual(TARGET)
    expect(wrapper.find('dialog').element.open).toBe(false)
  })

  it('stays open without emitting when the API call fails', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    trackingAPI.unmarkEpisodeWatched.mockRejectedValueOnce(new Error('boom'))

    const wrapper = mount(EpisodeUnwatchDialog)
    wrapper.vm.open(TARGET)
    await nextTick()

    wrapper.findComponent(ConfirmDialog).vm.$emit('confirm')
    await flushPromises()

    expect(wrapper.emitted('unwatched')).toBeUndefined()
    expect(wrapper.find('dialog').element.open).toBe(true)

    consoleError.mockRestore()
  })
})
