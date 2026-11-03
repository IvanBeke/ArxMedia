import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import IntegrationButton from '@/components/IntegrationButton.vue'
import { INTEGRATION_BRANDS, INTEGRATION_SERVICE } from '@/constants/integrations'

describe('IntegrationButton', () => {
  it('shows the label followed by the service icon', () => {
    const wrapper = mount(IntegrationButton, { props: { service: INTEGRATION_SERVICE.RADARR, label: 'Add to Radarr' } })

    const children = Array.from(wrapper.get('button').element.children)
    expect(children.map((child) => child.tagName)).toEqual(['SPAN', 'IMG'])
    expect(children[0]?.textContent).toBe('Add to Radarr')
    expect(wrapper.get('img').attributes('src')).toBe(INTEGRATION_BRANDS.radarr.icon)
    expect(wrapper.get('img').attributes('alt')).toBe('')
  })

  it('uses the service brand colour, stronger when active', async () => {
    const wrapper = mount(IntegrationButton, { props: { service: INTEGRATION_SERVICE.RADARR, label: 'Add to Radarr' } })

    expect(wrapper.get('button').classes()).toContain('text-radarr')
    expect(wrapper.get('button').classes()).not.toContain('bg-radarr/15')

    await wrapper.setProps({ active: true })

    expect(wrapper.get('button').classes()).toContain('bg-radarr/15')
  })

  it('uses each service\'s own icon and colour', () => {
    const wrapper = mount(IntegrationButton, { props: { service: INTEGRATION_SERVICE.SONARR, label: 'Add to Sonarr' } })

    expect(wrapper.get('img').attributes('src')).toBe('/static/branding/integrations/sonarr.webp')
    expect(wrapper.get('button').classes()).toContain('text-sonarr')
    expect(wrapper.get('button').classes()).not.toContain('text-radarr')
  })

  it('renders as a new-tab link when given a URL', () => {
    const wrapper = mount(IntegrationButton, {
      props: { service: INTEGRATION_SERVICE.JELLYFIN, label: 'Open in Jellyfin', href: 'https://jellyfin.example.com/web/#/details?id=1' },
    })

    const link = wrapper.get('a')
    expect(link.attributes('href')).toBe('https://jellyfin.example.com/web/#/details?id=1')
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toBe('noopener noreferrer')
    expect(link.classes()).toContain('text-jellyfin')
    expect(wrapper.get('img').attributes('src')).toBe('/static/branding/integrations/jellyfin.webp')
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('emits click events', async () => {
    const wrapper = mount(IntegrationButton, { props: { service: INTEGRATION_SERVICE.RADARR, label: 'Add to Radarr' } })

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('click')).toHaveLength(1)
  })
})
