import { describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach } from 'vitest'
import WatchSplitButton from '@/components/WatchSplitButton.vue'

beforeEach(() => {
  setActivePinia(createPinia())
})

function mountButton(props = {}) {
  return mount(WatchSplitButton, {
    props: { label: 'Mark watched', ...props },
  })
}

describe('WatchSplitButton', () => {
  it('emits trigger when the main half is clicked', async () => {
    const wrapper = mountButton()
    await wrapper.find('[role="group"] > button:first-child').trigger('click')

    expect(wrapper.emitted('trigger')).toHaveLength(1)
    expect(wrapper.emitted('select')).toBeUndefined()
  })

  it('opens the date menu from the chevron and emits the chosen option', async () => {
    const wrapper = mountButton({ releaseDate: '2020-05-01' })
    await wrapper.find('[aria-haspopup="menu"]').trigger('click')

    expect(wrapper.findAll('[role="menuitem"]').map((item) => item.text())).toEqual([
      'Just now',
      'Release date',
      'Unknown date',
      'Select date',
    ])

    await wrapper.findAll('[role="menuitem"]')[0]?.trigger('click')
    expect(wrapper.emitted('select')).toEqual([['now']])
  })

  it('renders the active label with brand styling when active', () => {
    const wrapper = mountButton({ active: true, label: 'Watched' })

    expect(wrapper.text()).toContain('Watched')
    expect(wrapper.find('[role="group"] > button:first-child').classes().join(' ')).toContain('bg-brand-500')
  })

  it('renders the danger variant with red styling and a cross icon', () => {
    const wrapper = mountButton({ label: 'Dropped', variant: 'danger' })
    const main = wrapper.find('[role="group"] > button:first-child')

    expect(wrapper.text()).toContain('Dropped')
    expect(main.classes().join(' ')).toContain('text-red-400')
    expect(main.find('svg path').attributes('d')).toBe('M6 18L18 6M6 6l12 12')
  })

  it('renders footer slot content below a divider', async () => {
    const wrapper = mount(WatchSplitButton, {
      props: { label: 'Watching' },
      slots: { menuFooter: '<button class="footer-action">Drop show</button>' },
    })
    await wrapper.find('[aria-haspopup="menu"]').trigger('click')

    expect(wrapper.find('.footer-action').exists()).toBe(true)
  })

  it('disables both halves while loading', () => {
    const wrapper = mountButton({ loading: true })
    const buttons = wrapper.findAll('[role="group"] > button')

    expect(buttons).toHaveLength(2)
    for (const button of buttons) {
      expect(button.attributes('disabled')).toBeDefined()
    }
  })
})
