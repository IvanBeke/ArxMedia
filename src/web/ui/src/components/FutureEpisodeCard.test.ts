import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, RouterLinkStub } from '@vue/test-utils'
import FutureEpisodeCard from '@/components/FutureEpisodeCard.vue'

const JELLYFIN_URL = 'https://jellyfin.example.com/web/index.html#/details?id=episode'

function mountCard(props: Record<string, unknown> = {}) {
  return mount(FutureEpisodeCard, {
    props: {
      showTitle: 'Breaking Bad',
      episodeTitle: 'Pilot',
      seasonNumber: 1,
      episodeNumber: 1,
      posterLinkTo: '/tv/1396/season/1/episode/1',
      ...props,
    },
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
}

describe('FutureEpisodeCard quick actions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows no actions by default', () => {
    const wrapper = mountCard()

    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.find('a[target="_blank"]').exists()).toBe(false)
  })

  it('shows the green watched action alone when there is no Jellyfin link', () => {
    const wrapper = mountCard({ showWatchAction: true })

    expect(wrapper.get('button').classes()).toContain('bg-emerald-700/90')
    expect(wrapper.find('a[target="_blank"]').exists()).toBe(false)
  })

  it('adds the purple Jellyfin play action next to the green one', () => {
    const wrapper = mountCard({ showWatchAction: true, jellyfinUrl: JELLYFIN_URL })

    const link = wrapper.get('a[target="_blank"]')
    expect(link.attributes('href')).toBe(JELLYFIN_URL)
    expect(link.classes()).toContain('bg-brand-500/95')
    expect(wrapper.get('button').classes()).toContain('bg-emerald-700/90')
  })

  it('emits watch from the green action', async () => {
    const wrapper = mountCard({ showWatchAction: true, jellyfinUrl: JELLYFIN_URL })

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('watch')).toHaveLength(1)
  })

  it('shows the Jellyfin action even when the watch action is off', () => {
    const wrapper = mountCard({ jellyfinUrl: JELLYFIN_URL })

    expect(wrapper.find('a[target="_blank"]').exists()).toBe(true)
    expect(wrapper.find('button').exists()).toBe(false)
  })
})
