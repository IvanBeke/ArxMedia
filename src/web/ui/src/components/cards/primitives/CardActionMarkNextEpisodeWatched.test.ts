import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import CardActionMarkNextEpisodeWatched from '@/components/cards/primitives/CardActionMarkNextEpisodeWatched.vue'

describe('CardActionMarkNextEpisodeWatched', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('is labelled like every other watched action', () => {
    const wrapper = mount(CardActionMarkNextEpisodeWatched)

    expect(wrapper.get('button').attributes('aria-label')).toBe('Mark as watched')
    expect(wrapper.get('button').attributes('title')).toBe('Mark as watched')
  })

  it('accepts a custom label', () => {
    const wrapper = mount(CardActionMarkNextEpisodeWatched, { props: { ariaLabel: 'Watched it' } })

    expect(wrapper.get('button').attributes('aria-label')).toBe('Watched it')
  })

  it('uses the green watched style with a checkmark icon', () => {
    const wrapper = mount(CardActionMarkNextEpisodeWatched)
    const button = wrapper.get('button')

    expect(button.classes()).toContain('bg-emerald-700/90')
    expect(button.classes()).not.toContain('bg-brand-500/95')
    expect(wrapper.find('svg.lucide-check').exists()).toBe(true)
  })

  it('emits both trigger events on click', async () => {
    const wrapper = mount(CardActionMarkNextEpisodeWatched)

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('trigger')).toHaveLength(1)
    expect(wrapper.emitted('action:upnext-watch')).toHaveLength(1)
  })

  it('is disabled and shows a spinner while loading', () => {
    const wrapper = mount(CardActionMarkNextEpisodeWatched, { props: { loading: true } })

    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    expect(wrapper.find('svg').exists()).toBe(false)
  })
})
