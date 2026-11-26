import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StatPie from '@/components/StatPie.vue'

describe('StatPie', () => {
  it('sizes each slice by its share and stacks them around the circle', () => {
    const wrapper = mount(StatPie, {
      props: { items: [
        { key: 'movie', label: 'Movies', value: 3, colorClass: 'text-blue-500' },
        { key: 'tv', label: 'Shows', value: 1, colorClass: 'text-brand-500' },
      ] },
    })

    const slices = wrapper.findAll('circle')
    expect(slices.map((slice) => slice.attributes('stroke-dasharray'))).toEqual(['75 25', '25 75'])
    expect(slices.map((slice) => slice.attributes('stroke-dashoffset'))).toEqual(['0', '-75'])
    expect(slices[0]!.classes()).toContain('text-blue-500')
  })

  it('fills the whole circle with a single non-empty slice', () => {
    const wrapper = mount(StatPie, {
      props: { items: [
        { key: 'movie', label: 'Movies', value: 5, colorClass: 'text-blue-500' },
        { key: 'tv', label: 'Shows', value: 0, colorClass: 'text-brand-500' },
      ] },
    })

    expect(wrapper.findAll('circle').map((slice) => slice.attributes('stroke-dasharray'))).toEqual(['100 0', '0 100'])
  })
})
