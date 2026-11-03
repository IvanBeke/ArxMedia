import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import CardActionOpenInJellyfin from '@/components/cards/primitives/CardActionOpenInJellyfin.vue'

const URL = 'https://jellyfin.example.com/web/index.html#/details?id=episode'

describe('CardActionOpenInJellyfin', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('opens the episode in Jellyfin in a new tab', () => {
    const wrapper = mount(CardActionOpenInJellyfin, { props: { url: URL } })

    const link = wrapper.get('a')
    expect(link.attributes('href')).toBe(URL)
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toBe('noopener noreferrer')
    expect(link.attributes('aria-label')).toBe('Open in Jellyfin')
  })

  it('keeps the purple play style', () => {
    const wrapper = mount(CardActionOpenInJellyfin, { props: { url: URL } })

    expect(wrapper.get('a').classes()).toContain('bg-brand-500/95')
    expect(wrapper.find('svg.lucide-play').exists()).toBe(true)
  })

  it('does not let the click reach the card', async () => {
    const parentClick = { count: 0 }
    const wrapper = mount({
      components: { CardActionOpenInJellyfin },
      setup: () => ({ url: URL, parentClick }),
      template: '<div @click="parentClick.count++"><CardActionOpenInJellyfin :url="url" /></div>',
    })

    await wrapper.get('a').trigger('click')

    expect(parentClick.count).toBe(0)
  })
})
