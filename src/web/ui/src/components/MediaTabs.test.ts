import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import MediaTabs from '@/components/MediaTabs.vue'

describe('MediaTabs', () => {
  it('marks the active tab and emits selection', async () => {
    const wrapper = mount(MediaTabs, {
      props: {
        modelValue: 'overview',
        tabs: [
          { id: 'overview', label: 'Overview' },
          { id: 'cast', label: 'Cast', count: 12 },
        ],
      },
    })

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs).toHaveLength(2)
    expect(tabs[0]?.attributes('aria-selected')).toBe('true')
    expect(wrapper.text()).toContain('(12)')

    await tabs[1]?.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['cast']])
  })

  it('moves with arrow keys', async () => {
    const wrapper = mount(MediaTabs, {
      props: {
        modelValue: 'overview',
        tabs: [
          { id: 'overview', label: 'Overview' },
          { id: 'cast', label: 'Cast' },
        ],
      },
    })

    await wrapper.find('[role="tablist"]').trigger('keydown', { key: 'ArrowRight' })
    expect(wrapper.emitted('update:modelValue')).toEqual([['cast']])
  })
})
