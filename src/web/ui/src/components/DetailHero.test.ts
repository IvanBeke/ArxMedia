import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DetailHero from '@/components/DetailHero.vue'

describe('DetailHero', () => {
  it('sizes the backdrop from hero content instead of a fixed minimum height', () => {
    const wrapper = mount(DetailHero, {
      slots: { title: '<h1>Short profile</h1>' },
    })

    expect(wrapper.classes()).toContain('grid')
    expect(wrapper.find('.relative.row-start-1').classes()).toContain('col-start-1')
    expect(wrapper.find('.relative.row-start-1').classes()).not.toContain('min-h-72')
    expect(wrapper.find('.relative.row-start-1').classes()).not.toContain('md:min-h-[28rem]')
    expect(wrapper.find('.max-w-7xl').classes()).toContain('row-start-1')
    expect(wrapper.find('.max-w-7xl').classes()).toContain('w-full')
    expect(wrapper.find('.max-w-7xl').classes()).toContain('pt-12')
  })

  it('keeps bare heroes in normal flow without a backdrop', () => {
    const wrapper = mount(DetailHero, {
      props: { bare: true },
      slots: { title: '<h1>Short profile</h1>' },
    })

    expect(wrapper.classes()).not.toContain('grid')
    expect(wrapper.find('.relative.row-start-1').exists()).toBe(false)
    expect(wrapper.find('.max-w-7xl').classes()).toContain('py-8')
  })
})
