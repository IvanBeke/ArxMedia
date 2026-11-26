import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StatsState from '@/components/StatsState.vue'

const slots = { default: '<p class="content">chart</p>' }

describe('StatsState', () => {
  it('shows its content by default', () => {
    const wrapper = mount(StatsState, { slots })

    expect(wrapper.find('.content').exists()).toBe(true)
  })

  it('shows a skeleton instead of the content while loading', () => {
    const wrapper = mount(StatsState, { props: { loading: true }, slots })

    expect(wrapper.find('.skeleton').exists()).toBe(true)
    expect(wrapper.find('.content').exists()).toBe(false)
  })

  it('shows an error with a retry button that emits retry', async () => {
    const wrapper = mount(StatsState, { props: { error: true }, slots })

    expect(wrapper.get('[role="alert"]').text()).toContain('Could not load stats.')
    expect(wrapper.find('.content').exists()).toBe(false)

    await wrapper.get('[role="alert"] button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('sizes the skeleton as asked', () => {
    const wrapper = mount(StatsState, { props: { loading: true, skeletonClass: 'flex-1' }, slots })

    expect(wrapper.get('.skeleton').classes()).toContain('flex-1')
    expect(wrapper.get('.skeleton').classes()).not.toContain('h-32')
  })
})
