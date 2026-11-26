import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StatLegend from '@/components/StatLegend.vue'
import { toSlices } from '@/utils/statShares'

describe('StatLegend', () => {
  it('lists each slice with its label, display text or value, and percentage', () => {
    const slices = toSlices([
      { key: 'movies', label: 'Movies', value: 30, colorClass: 'text-blue-500', display: '30m' },
      { key: 'episodes', label: 'Episodes', value: 70, colorClass: 'text-brand-500' },
    ])
    const wrapper = mount(StatLegend, { props: { slices } })

    const rows = wrapper.findAll('li').map((row) => row.findAll('span').slice(1).map((cell) => cell.text()))
    expect(rows).toEqual([['Movies', '30m', '30%'], ['Episodes', '70', '70%']])
  })

  it('colours the dot with the slice colour and passes classes on to the list', () => {
    const slices = toSlices([{ key: 'a', label: 'A', value: 1, colorClass: 'text-emerald-600' }])
    const wrapper = mount(StatLegend, { props: { slices }, attrs: { class: 'space-y-2' } })

    expect(wrapper.classes()).toContain('space-y-2')
    expect(wrapper.get('li').classes()).toContain('text-emerald-600')
    expect(wrapper.get('li span').classes()).toContain('bg-current')
  })
})
