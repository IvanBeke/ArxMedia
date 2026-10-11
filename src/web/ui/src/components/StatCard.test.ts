import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StatCard from '@/components/StatCard.vue'

describe('StatCard', () => {
  it('renders the value and title', () => {
    const wrapper = mount(StatCard, { props: { title: 'Watch time', value: '2h 30m' } })

    expect(wrapper.text()).toContain('2h 30m')
    expect(wrapper.text()).toContain('Watch time')
  })

  it('renders numeric values', () => {
    const wrapper = mount(StatCard, { props: { title: 'Movies Watched', value: 42 } })

    expect(wrapper.text()).toContain('42')
  })
})
