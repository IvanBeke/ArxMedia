import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import FlashToast from '@/components/FlashToast.vue'

describe('FlashToast', () => {
  it('renders only non-empty messages with roles that screen readers announce', () => {
    const wrapper = mount(FlashToast, {
      props: {
        messages: [
          { text: 'Added to watchlist', kind: 'success' },
          { text: '', kind: 'success' },
          { text: null, kind: 'error' },
          { text: 'Could not drop this show.', kind: 'error' },
        ],
      },
    })

    expect(wrapper.get('[role="status"]').text()).toBe('Added to watchlist')
    expect(wrapper.get('[role="alert"]').text()).toBe('Could not drop this show.')
    expect(wrapper.findAll('[role]')).toHaveLength(2)
  })

  it('is fixed to the viewport so messages never shift the page', () => {
    const wrapper = mount(FlashToast, { props: { messages: [] } })

    expect(wrapper.classes()).toContain('fixed')
  })
})
