import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
})

function mountDialog(props = {}) {
  return mount(ConfirmDialog, {
    props: {
      title: 'Remove this episode from history?',
      message: 'This will remove this episode from your watched history.',
      ...props,
    },
  })
}

describe('ConfirmDialog', () => {
  it('renders the copy and button labels', () => {
    const wrapper = mountDialog({
      confirmLabel: 'Unwatch',
      cancelLabel: 'Keep watched',
    })

    expect(wrapper.text()).toContain('Remove this episode from history?')
    expect(wrapper.text()).toContain('This will remove this episode from your watched history.')
    expect(wrapper.findAll('button').map((button) => button.text())).toEqual(['Keep watched', 'Unwatch'])
  })

  it('opens as a modal via the exposed method', async () => {
    const wrapper = mountDialog()
    wrapper.vm.showModal()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('dialog').element.open).toBe(true)
  })

  it('emits confirm without closing itself', async () => {
    const wrapper = mountDialog()
    wrapper.vm.showModal()
    await wrapper.vm.$nextTick()

    await wrapper.findAll('button')[1].trigger('click')

    expect(wrapper.emitted('confirm')).toHaveLength(1)
    expect(wrapper.find('dialog').element.open).toBe(true)
  })

  it('closes on cancel', async () => {
    const wrapper = mountDialog()
    wrapper.vm.showModal()
    await wrapper.vm.$nextTick()

    await wrapper.findAll('button')[0].trigger('click')

    expect(wrapper.find('dialog').element.open).toBe(false)
    expect(wrapper.emitted('confirm')).toBeUndefined()
  })

  it('disables the confirm button while loading', () => {
    const wrapper = mountDialog({ loading: true, loadingLabel: 'Unwatching...', confirmLabel: 'Unwatch' })
    const buttons = wrapper.findAll('button')

    expect(buttons[1].attributes('disabled')).toBeDefined()
    expect(buttons[1].text()).toBe('Unwatching...')
  })
})
