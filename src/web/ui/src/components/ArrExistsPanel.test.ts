import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ArrExistsPanel from '@/components/ArrExistsPanel.vue'

const PROPS = { message: 'This movie is already in Radarr.', openLabel: 'Open in Radarr', removeLabel: 'Remove from Radarr' }

describe('ArrExistsPanel', () => {
  it('shows the message and the path', () => {
    const wrapper = mount(ArrExistsPanel, { props: { ...PROPS, path: '/movies/The Matrix (1999)' } })

    expect(wrapper.text()).toContain('This movie is already in Radarr.')
    expect(wrapper.text()).toContain('/movies/The Matrix (1999)')
  })

  it('opens the item in a new tab', () => {
    const wrapper = mount(ArrExistsPanel, { props: { ...PROPS, url: 'https://radarr.example.com/movie/603' } })

    const link = wrapper.get('a')
    expect(link.text()).toBe('Open in Radarr')
    expect(link.attributes('href')).toBe('https://radarr.example.com/movie/603')
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toBe('noopener noreferrer')
  })

  it('omits the link when there is no URL', () => {
    const wrapper = mount(ArrExistsPanel, { props: PROPS })

    expect(wrapper.find('a').exists()).toBe(false)
  })

  it('emits remove from the remove button', async () => {
    const wrapper = mount(ArrExistsPanel, { props: PROPS })

    await wrapper.get('button').trigger('click')

    expect(wrapper.get('button').text()).toBe('Remove from Radarr')
    expect(wrapper.emitted('remove')).toHaveLength(1)
  })
})
