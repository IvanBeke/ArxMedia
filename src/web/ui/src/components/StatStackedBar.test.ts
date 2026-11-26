import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StatStackedBar from '@/components/StatStackedBar.vue'

const items = [
  { key: 'movies', label: 'Movies', value: 30, colorClass: 'text-blue-500', display: '30m' },
  { key: 'episodes', label: 'Episodes', value: 70, colorClass: 'text-brand-500' },
]

describe('StatStackedBar', () => {
  it('sizes each segment by its share and colours it', () => {
    const wrapper = mount(StatStackedBar, { props: { items } })

    const segments = wrapper.findAll('.bg-current.min-w-1')
    expect(segments.map((segment) => segment.attributes('style'))).toEqual(['width: 30%;', 'width: 70%;'])
    expect(segments[0]!.classes()).toContain('text-blue-500')
    expect(segments[0]!.attributes('title')).toBe('Movies: 30m (30%)')
  })

  it('gives an empty slice a zero-width segment', () => {
    const wrapper = mount(StatStackedBar, {
      props: { items: [
        { key: 'a', label: 'A', value: 5, colorClass: 'text-blue-500' },
        { key: 'b', label: 'B', value: 0, colorClass: 'text-brand-500' },
      ] },
    })

    expect(wrapper.findAll('.bg-current.min-w-1').map((segment) => segment.attributes('style'))).toEqual(['width: 100%;', 'width: 0%;'])
    expect(wrapper.findAll('li')[1]!.text()).toContain('0%')
  })
})
