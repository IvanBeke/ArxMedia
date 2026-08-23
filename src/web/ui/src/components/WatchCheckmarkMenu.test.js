import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import WatchCheckmarkMenu from '@/components/WatchCheckmarkMenu.vue'
import WatchMenu from '@/components/WatchMenu.vue'

beforeEach(() => {
  setActivePinia(createPinia())
})

function mountCheckmark(props = {}) {
  return mount(WatchCheckmarkMenu, { props })
}

describe('WatchCheckmarkMenu', () => {
  it('opens the options menu for an unwatched item', async () => {
    const wrapper = mountCheckmark({ watched: false, releaseDate: '2020-01-01' })
    await wrapper.find('button').trigger('click')

    const menu = wrapper.findComponent(WatchMenu)
    expect(menu.find('[role="menu"]').exists()).toBe(true)
    expect(wrapper.emitted('unwatch')).toBeUndefined()
  })

  it('emits unwatch straight away for a watched item without showing options', async () => {
    const wrapper = mountCheckmark({ watched: true })
    await wrapper.find('button').trigger('click')

    expect(wrapper.emitted('unwatch')).toHaveLength(1)
    expect(wrapper.find('[role="menu"]').exists()).toBe(false)
  })

  it('forwards select events from the inner menu', async () => {
    const wrapper = mountCheckmark({ watched: false })
    wrapper.findComponent(WatchMenu).vm.$emit('select', 'now')
    await nextTick()

    expect(wrapper.emitted('select')).toEqual([['now']])
  })
})
