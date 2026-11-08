import { afterEach, describe, expect, it } from 'vitest'
import { defineComponent, nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { usePageTitle } from '@/composables/usePageTitle'

function mountWithTitle(title: Parameters<typeof usePageTitle>[0]) {
  return mount(defineComponent({
    setup() {
      usePageTitle(title)
      return () => null
    },
  }))
}

describe('usePageTitle', () => {
  afterEach(() => {
    document.title = ''
  })

  it('appends the app name to the page title', () => {
    mountWithTitle('Dashboard')

    expect(document.title).toBe('Dashboard · ArxMedia')
  })

  it('falls back to the app name when the title is empty', async () => {
    const title = ref<string | null>(null)
    mountWithTitle(title)
    expect(document.title).toBe('ArxMedia')

    title.value = '   '
    await nextTick()
    expect(document.title).toBe('ArxMedia')
  })

  it('follows reactive changes', async () => {
    const title = ref<string | null>(null)
    mountWithTitle(() => title.value)
    expect(document.title).toBe('ArxMedia')

    title.value = 'Dune'
    await nextTick()
    expect(document.title).toBe('Dune · ArxMedia')
  })

  it('keeps the title after unmount so the incoming view owns it', () => {
    const wrapper = mountWithTitle('History')
    wrapper.unmount()

    expect(document.title).toBe('History · ArxMedia')
  })
})
