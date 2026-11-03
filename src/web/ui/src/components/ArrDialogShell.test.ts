import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ArrDialogShell from '@/components/ArrDialogShell.vue'

function mountShell() {
  return mount(ArrDialogShell, {
    props: { heading: 'Add to Radarr', title: 'The Matrix' },
    slots: { default: '<p class="content">Form goes here</p>' },
  })
}

describe('ArrDialogShell', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the heading, the title and the slot content', () => {
    const wrapper = mountShell()

    expect(wrapper.get('h2').text()).toBe('Add to Radarr')
    expect(wrapper.text()).toContain('The Matrix')
    expect(wrapper.get('.content').text()).toBe('Form goes here')
  })

  it('labels the dialog with its heading', () => {
    const wrapper = mountShell()

    expect(wrapper.get('dialog').attributes('aria-labelledby')).toBe(wrapper.get('h2').attributes('id'))
  })

  it('opens as a modal and closes from the exposed methods', async () => {
    const wrapper = mountShell()

    wrapper.vm.showModal()
    await wrapper.vm.$nextTick()
    expect(wrapper.get('dialog').element.open).toBe(true)

    wrapper.vm.close()
    await wrapper.vm.$nextTick()
    expect(wrapper.get('dialog').element.open).toBe(false)
  })

  it('closes from the close button', async () => {
    const wrapper = mountShell()
    wrapper.vm.showModal()
    await wrapper.vm.$nextTick()

    await wrapper.get('button[aria-label="Cancel"]').trigger('click')

    expect(wrapper.get('dialog').element.open).toBe(false)
  })
})
