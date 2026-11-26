import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StatsSection from '@/components/StatsSection.vue'

const slots = { default: '<p class="content">chart</p>' }

describe('StatsSection', () => {
  it('shows the title and its content', () => {
    const wrapper = mount(StatsSection, { props: { title: 'Ratings' }, slots })

    expect(wrapper.get('h2').text()).toBe('Ratings')
    expect(wrapper.find('.content').exists()).toBe(true)
  })

  it('shows a skeleton instead of the content while loading', () => {
    const wrapper = mount(StatsSection, { props: { title: 'Ratings', loading: true }, slots })

    expect(wrapper.find('.skeleton').exists()).toBe(true)
    expect(wrapper.find('.content').exists()).toBe(false)
  })

  it('shows an error with a retry button that emits retry', async () => {
    const wrapper = mount(StatsSection, { props: { title: 'Ratings', error: true }, slots })

    expect(wrapper.get('[role="alert"]').text()).toContain('Could not load stats.')
    expect(wrapper.find('.content').exists()).toBe(false)

    await wrapper.get('[role="alert"] button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })
})
