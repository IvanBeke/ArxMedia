import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StatColumns from '@/components/StatColumns.vue'

describe('StatColumns', () => {
  it('scales column heights, shows labels and titles, and mutes empty columns', () => {
    const wrapper = mount(StatColumns, {
      props: { items: [
        { key: '1', label: 'Jan', value: 4, title: 'January: 4' },
        { key: '2', label: 'Feb', value: 2 },
        { key: '3', label: 'Mar', value: 0 },
      ] },
    })

    const columns = wrapper.findAll('li')
    expect(columns[0]!.attributes('title')).toBe('January: 4')
    expect(columns.map((column) => column.get('div > div').attributes('style'))).toEqual([
      'height: 100%;', 'height: 50%;', 'height: 2%;',
    ])
    expect(columns[2]!.get('div > div').classes()).toContain('bg-surface-200')
    expect(wrapper.text()).toContain('Jan')
    expect(wrapper.text()).toContain('4')
  })

  it('applies a custom bar colour and keeps the value above the bar in compact mode', () => {
    const wrapper = mount(StatColumns, {
      props: { compact: true, barClass: 'bg-blue-500', items: [{ key: '1', label: '00', value: 4 }] },
    })

    expect(wrapper.get('li div > div').classes()).toContain('bg-blue-500')
    expect(wrapper.get('li div > div').classes()).not.toContain('bg-brand-500')
    expect(wrapper.findAll('li span').map((span) => span.text())).toEqual(['4', '00'])
  })

  it('stacks segments bottom first, sized by their share of the column total', () => {
    const wrapper = mount(StatColumns, {
      props: { items: [
        { key: '1', label: 'Jan', value: 4, segments: [{ value: 1, barClass: 'bg-brand-500' }, { value: 3, barClass: 'bg-blue-500' }] },
        { key: '2', label: 'Feb', value: 2, segments: [{ value: 2, barClass: 'bg-brand-500' }, { value: 0, barClass: 'bg-blue-500' }] },
      ] },
    })

    const columns = wrapper.findAll('li')
    expect(columns[0]!.get('div > div').attributes('style')).toBe('height: 100%;')
    expect(columns[1]!.get('div > div').attributes('style')).toBe('height: 50%;')
    const segments = columns[0]!.findAll('div > div > div')
    expect(segments.map((segment) => segment.classes().find((name) => name.startsWith('bg-')))).toEqual(['bg-brand-500', 'bg-blue-500'])
    expect(segments.map((segment) => segment.attributes('style'))).toEqual(['height: 25%;', 'height: 75%;'])
    expect(columns[0]!.get('div > div').classes()).toContain('flex-col-reverse')
  })

  it('falls back to a muted bar for a stacked column without any value', () => {
    const wrapper = mount(StatColumns, {
      props: { items: [{ key: '1', label: 'Jan', value: 0, segments: [{ value: 0, barClass: 'bg-blue-500' }] }] },
    })

    expect(wrapper.get('li div > div').classes()).toContain('bg-surface-200')
  })
})
