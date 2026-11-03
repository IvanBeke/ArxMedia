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

  it('emits click events', async () => {
    const wrapper = mount(IntegrationButton, { props: { service: INTEGRATION_SERVICE.RADARR, label: 'Add to Radarr' } })

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('click')).toHaveLength(1)
  })
})
