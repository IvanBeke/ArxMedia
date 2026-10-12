import { describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import AddToListPopover from '@/components/AddToListPopover.vue'

vi.mock('@/api', () => ({
  trackingAPI: {
    getLists: vi.fn().mockResolvedValue({ count: 0, next: null, previous: null, results: [] }),
    addToList: vi.fn(),
    createList: vi.fn(),
    removeFromList: vi.fn(),
  },
}))

function mountPopover() {
  return mount(AddToListPopover, {
    props: { mediaType: 'movie', tmdbId: 42, startOpen: true },
    global: { plugins: [createPinia()] },
  })
}

describe('AddToListPopover', () => {
  it('keeps the desktop dropdown anchored to the button', () => {
    const panel = mountPopover().find('.absolute')

    expect(panel.exists()).toBe(true)
    expect(panel.classes()).toContain('right-0')
    expect(panel.classes()).toContain('w-72')
  })

  it('passes positioning through to the actions bar below the sm breakpoint', () => {
    const wrapper = mountPopover()

    expect(wrapper.classes()).toContain('max-sm:static')
  })

  it('docks the panel above the actions row below the sm breakpoint', () => {
    const panel = mountPopover().find('.absolute')

    expect(panel.classes()).toContain('max-sm:inset-x-0')
    expect(panel.classes()).toContain('max-sm:bottom-full')
    expect(panel.classes()).toContain('max-sm:w-auto')
  })

  it('keeps modal mode full width without floating positioning', () => {
    const wrapper = mount(AddToListPopover, {
      props: { mediaType: 'movie', tmdbId: 42, modalMode: true },
      global: { plugins: [createPinia()] },
    })

    expect(wrapper.find('.absolute').exists()).toBe(false)
    expect(wrapper.find('.w-full').exists()).toBe(true)
  })
})
