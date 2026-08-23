import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import WatchMenu from '@/components/WatchMenu.vue'

beforeEach(() => {
  setActivePinia(createPinia())
})

function mountMenu(props = {}) {
  return mount(WatchMenu, {
    props,
    slots: { default: '<span>Trigger</span>' },
  })
}

describe('WatchMenu', () => {
  it('shows now, unknown and date options in order when there is no release date', async () => {
    const wrapper = mountMenu()
    await wrapper.find('button').trigger('click')

    expect(wrapper.findAll('[role="menuitem"]').map((item) => item.text())).toEqual([
      'Just now',
      'Unknown date',
      'Select date',
    ])
  })

  it('places the release option before unknown date', async () => {
    const wrapper = mountMenu({ releaseDate: '2020-05-01' })
    await wrapper.find('button').trigger('click')

    expect(wrapper.findAll('[role="menuitem"]').map((item) => item.text())).toEqual([
      'Just now',
      'Release date',
      'Unknown date',
      'Select date',
    ])
  })

  it('emits the chosen option value and closes the menu', async () => {
    const wrapper = mountMenu()
    await wrapper.find('button').trigger('click')
    await wrapper.findAll('[role="menuitem"]')[1].trigger('click')

    expect(wrapper.emitted('select')).toEqual([['unknown']])
    expect(wrapper.find('[role="menu"]').exists()).toBe(false)
  })

  it('emits trigger directly without opening the menu in direct-trigger mode', async () => {
    const wrapper = mountMenu({ directTrigger: true })
    await wrapper.find('button').trigger('click')

    expect(wrapper.emitted('trigger')).toHaveLength(1)
    expect(wrapper.emitted('select')).toBeUndefined()
    expect(wrapper.find('[role="menu"]').exists()).toBe(false)
  })

  it('ignores clicks while disabled', async () => {
    const wrapper = mountMenu({ disabled: true, directTrigger: true })
    await wrapper.find('button').trigger('click')

    expect(wrapper.emitted('trigger')).toBeUndefined()
  })
})
